"""
Reviewer agent implementation.

The ReviewerAgent is responsible for evaluating the results of code patches
and test executions, providing structured feedback to guide the development
process. It analyzes test results, code quality metrics, and overall step
success to determine whether to proceed, retry with feedback, or escalate
back to the planner.

The agent provides detailed feedback that can be used by the DeveloperAgent
to improve subsequent patch attempts, and can recommend when to return to
the PlannerAgent for plan revision.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional, Dict
from enum import Enum
import logging

from ..plan_parser import Step


class ReviewDecision(Enum):
    """Possible decisions from the reviewer agent."""
    
    ACCEPT = "accept"           # Step completed successfully
    RETRY = "retry"             # Retry with feedback
    ESCALATE_TO_PLANNER = "escalate_to_planner"  # Need to revise plan
    FAIL = "fail"               # Unrecoverable failure


@dataclass
class TestResult:
    """Represents the result of a test execution."""
    
    test_type: str              # e.g., "pest", "phpstan", "jest"
    status: str                 # "passed" or "failed"
    output: str                 # Test output/logs
    details: Optional[Dict[str, Any]] = None


@dataclass
class ReviewResult:
    """Result of a code review evaluation."""
    
    decision: ReviewDecision
    feedback: str               # Detailed feedback for improvement
    confidence: float           # Confidence in the decision (0.0-1.0)
    test_summary: Dict[str, Any]  # Summary of test results
    suggestions: List[str]      # Specific suggestions for improvement
    should_escalate: bool = False  # Whether to escalate to planner


class ReviewerAgent:
    """
    Evaluate patch results and provide structured feedback.
    
    The ReviewerAgent analyzes test results, code quality, and step outcomes
    to provide actionable feedback for the development process.
    """
    
    def __init__(
        self,
        llm_router: Any,
        max_retry_attempts: int = 3,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        """
        Initialize the reviewer agent.
        
        Args:
            llm_router: Component for LLM interactions
            max_retry_attempts: Maximum retry attempts before escalation
            logger: Optional logger instance
        """
        self.llm_router = llm_router
        self.max_retry_attempts = max_retry_attempts
        self.log = logger or logging.getLogger(__name__)
    
    async def review_step_result(
        self,
        step: Step,
        patch_text: str,
        test_results: List[TestResult],
        attempt_number: int = 1,
        previous_feedback: Optional[str] = None,
        stack: str = "generic",
    ) -> ReviewResult:
        """
        Review the results of a development step.
        
        Args:
            step: The step that was executed
            patch_text: The generated patch
            test_results: Results from test execution
            attempt_number: Current attempt number for this step
            previous_feedback: Feedback from previous attempts
            stack: Technology stack being used
            
        Returns:
            ReviewResult with decision and feedback
        """
        # Analyze test results
        test_summary = self._analyze_test_results(test_results)
        all_tests_passed = test_summary["all_passed"]
        
        # Determine if we should escalate based on attempt count
        should_escalate = attempt_number >= self.max_retry_attempts
        
        # If all tests passed, accept the step
        if all_tests_passed:
            return ReviewResult(
                decision=ReviewDecision.ACCEPT,
                feedback="All tests passed successfully. Step completed.",
                confidence=0.95,
                test_summary=test_summary,
                suggestions=[],
                should_escalate=False
            )
        
        # If we've reached max attempts, decide between escalation and failure
        if should_escalate:
            # Use LLM to determine if this requires plan revision
            escalation_decision = await self._should_escalate_to_planner(
                step, patch_text, test_results, previous_feedback, stack
            )
            
            if escalation_decision["should_escalate"]:
                return ReviewResult(
                    decision=ReviewDecision.ESCALATE_TO_PLANNER,
                    feedback=escalation_decision["feedback"],
                    confidence=escalation_decision["confidence"],
                    test_summary=test_summary,
                    suggestions=escalation_decision["suggestions"],
                    should_escalate=True
                )
            else:
                return ReviewResult(
                    decision=ReviewDecision.FAIL,
                    feedback=f"Step failed after {attempt_number} attempts. " + escalation_decision["feedback"],
                    confidence=0.8,
                    test_summary=test_summary,
                    suggestions=[],
                    should_escalate=False
                )
        
        # Generate feedback for retry
        feedback_result = await self._generate_retry_feedback(
            step, patch_text, test_results, previous_feedback, stack
        )
        
        return ReviewResult(
            decision=ReviewDecision.RETRY,
            feedback=feedback_result["feedback"],
            confidence=feedback_result["confidence"],
            test_summary=test_summary,
            suggestions=feedback_result["suggestions"],
            should_escalate=False
        )
    
    def _analyze_test_results(self, test_results: List[TestResult]) -> Dict[str, Any]:
        """Analyze test results and provide summary."""
        if not test_results:
            return {
                "all_passed": False,
                "total_tests": 0,
                "passed_tests": 0,
                "failed_tests": 0,
                "test_types": [],
                "failures": []
            }
        
        passed_count = sum(1 for result in test_results if result.status == "passed")
        failed_count = len(test_results) - passed_count
        
        failures = []
        for result in test_results:
            if result.status == "failed":
                failures.append({
                    "test_type": result.test_type,
                    "output": result.output[:500],  # Truncate long outputs
                    "details": result.details
                })
        
        return {
            "all_passed": failed_count == 0,
            "total_tests": len(test_results),
            "passed_tests": passed_count,
            "failed_tests": failed_count,
            "test_types": [result.test_type for result in test_results],
            "failures": failures
        }
    
    async def _should_escalate_to_planner(
        self,
        step: Step,
        patch_text: str,
        test_results: List[TestResult],
        previous_feedback: Optional[str],
        stack: str,
    ) -> Dict[str, Any]:
        """
        Use LLM to determine if the issue requires plan revision.
        """
        # Prepare test failure summary
        failures_text = "\n".join([
            f"- {result.test_type}: {result.output[:200]}..."
            for result in test_results if result.status == "failed"
        ])
        
        prompt = f"""
You are a senior technical reviewer analyzing a development step that has failed multiple times.

STEP DETAILS:
- Step #{step.id}: {step.description}
- Technology Stack: {stack}
- Attempt: Final attempt before escalation

PATCH APPLIED:
{patch_text[:1000]}...

TEST FAILURES:
{failures_text}

PREVIOUS FEEDBACK:
{previous_feedback or "None"}

ANALYSIS REQUIRED:
Determine if this failure indicates:
1. A fundamental issue with the step design that requires plan revision (ESCALATE)
2. A technical implementation issue that should be marked as failed (FAIL)

Consider these factors:
- Are the test failures due to architectural/design issues?
- Does the step conflict with existing code structure?
- Are the requirements unclear or impossible to implement?
- Would breaking this step into smaller steps help?

Respond in JSON format:
{{
    "should_escalate": true/false,
    "confidence": 0.0-1.0,
    "feedback": "Detailed explanation of the decision",
    "suggestions": ["suggestion1", "suggestion2", ...]
}}
"""
        
        try:
            messages = [{"role": "user", "content": prompt}]
            response = await self._call_llm(messages)
            
            # Parse JSON response
            import json
            result = json.loads(response)
            
            return {
                "should_escalate": result.get("should_escalate", False),
                "confidence": result.get("confidence", 0.5),
                "feedback": result.get("feedback", "Unable to determine escalation need"),
                "suggestions": result.get("suggestions", [])
            }
            
        except Exception as e:
            self.log.warning(f"Error in escalation analysis: {e}")
            # Default to not escalating on error
            return {
                "should_escalate": False,
                "confidence": 0.3,
                "feedback": f"Unable to analyze escalation need due to error: {e}",
                "suggestions": []
            }
    
    async def _generate_retry_feedback(
        self,
        step: Step,
        patch_text: str,
        test_results: List[TestResult],
        previous_feedback: Optional[str],
        stack: str,
    ) -> Dict[str, Any]:
        """
        Generate specific feedback for retry attempts.
        """
        # Prepare detailed test failure information
        failures_detail = []
        for result in test_results:
            if result.status == "failed":
                failures_detail.append(f"""
{result.test_type.upper()} FAILURE:
{result.output}
""")
        
        failures_text = "\n".join(failures_detail)
        
        prompt = f"""
You are a senior code reviewer providing feedback to improve a failing code patch.

STEP CONTEXT:
- Step #{step.id}: {step.description}
- Technology Stack: {stack}
- Files involved: {', '.join(step.files_involved) if step.files_involved else 'Not specified'}

CURRENT PATCH:
{patch_text}

TEST FAILURES:
{failures_text}

PREVIOUS FEEDBACK (if any):
{previous_feedback or "This is the first attempt"}

TASK:
Provide specific, actionable feedback to fix the test failures. Focus on:
1. Root cause analysis of each failure
2. Specific code changes needed
3. Best practices for the {stack} stack
4. Common pitfalls to avoid

Respond in JSON format:
{{
    "feedback": "Detailed, actionable feedback for the developer",
    "confidence": 0.0-1.0,
    "suggestions": [
        "Specific suggestion 1",
        "Specific suggestion 2",
        ...
    ]
}}
"""
        
        try:
            messages = [{"role": "user", "content": prompt}]
            response = await self._call_llm(messages)
            
            # Parse JSON response
            import json
            result = json.loads(response)
            
            return {
                "feedback": result.get("feedback", "Please review test failures and adjust implementation"),
                "confidence": result.get("confidence", 0.7),
                "suggestions": result.get("suggestions", [])
            }
            
        except Exception as e:
            self.log.warning(f"Error generating retry feedback: {e}")
            # Fallback to basic feedback
            return {
                "feedback": f"Tests failed. Please review the following failures and adjust your implementation:\n{failures_text[:500]}",
                "confidence": 0.5,
                "suggestions": ["Review test failures", "Check syntax and logic", "Ensure proper imports"]
            }
    
    async def _call_llm(self, messages: List[Dict[str, str]]) -> str:
        """Helper method to call LLM with error handling."""
        try:
            result = self.llm_router.generate(messages)
            if hasattr(result, "__await__"):
                return await result
            else:
                return result
        except Exception as e:
            self.log.error(f"LLM call failed: {e}")
            raise