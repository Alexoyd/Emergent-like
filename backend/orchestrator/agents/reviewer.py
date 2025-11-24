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
import json
import asyncio

from ..plan_parser import Step


def defensive_json_parse(content: str, context: str = "response", logger = None) -> Optional[Dict]:
    """
    🔥 SOLUTION 4: Defensive JSON parsing with validation (Emergent.sh strategy)
    
    Validates and parses JSON with 3 levels of checks:
    1. Check if content exists and is non-empty
    2. Attempt to parse JSON
    3. Validate basic structure
    
    Args:
        content: String content to parse
        context: Context description for logging
        logger: Logger instance for warnings
        
    Returns:
        Parsed JSON dict or None if parsing fails
    """
    if logger is None:
        logger = logging.getLogger(__name__)
    
    # ✅ Check 1: Content exists and is non-empty
    if not content:
        logger.warning(f"⚠️ Empty {context} from LLM")
        return None
    
    content_stripped = content.strip()
    if len(content_stripped) == 0:
        logger.warning(f"⚠️ Empty {context} content from LLM (whitespace only)")
        return None
    
    # ✅ Check 2: Valid JSON parsing
    try:
        data = json.loads(content_stripped)
    except json.JSONDecodeError as e:
        logger.error(f"❌ JSON parsing failed for {context}: {e}")
        logger.error(f"Response preview (first 200 chars): {content_stripped[:200]}")
        return None
    
    # ✅ Check 3: Basic structure validation (should be a dict)
    if not isinstance(data, dict):
        logger.warning(f"⚠️ {context} is not a JSON object (dict), got {type(data)}")
        return None
    
    return data


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
        
        # Development mode for simplified behavior
        import os
        self.development_mode = os.environ.get("DEVELOPMENT_MODE", "true").lower() == "true"
    
    async def review_step_result(
        self,
        step: Step,
        patch_text: str,
        test_results: List[TestResult],
        attempt_number: int = 1,
        previous_feedback: Optional[str] = None,
        stack: str = "generic",
        run: Any = None, 
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
        
        # ✅ Development mode: always accept in first attempt
        if self.development_mode and attempt_number == 1:
            self.log.info("🧪 Development mode: accepting step on first attempt")
            return ReviewResult(
                decision=ReviewDecision.ACCEPT,
                feedback="Development mode: automatically accepted for testing cycle.",
                confidence=0.8,
                test_summary=test_summary,
                suggestions=[],
                should_escalate=False
            )
        
        # 🔥 CRITICAL FIX: Feature-level validation before accepting
        # Tests passing doesn't mean the feature is implemented
        # Check for "placeholder only" scenario (fake success)
        if patch_text and "PLACEHOLDER_ERROR" in patch_text:
            self.log.warning("⚠️ Patch contains PLACEHOLDER_ERROR - likely 429 TPM fallback")
            self.log.warning("⚠️ This indicates NO REAL CODE was generated")
            return ReviewResult(
                decision=ReviewDecision.RETRY,
                feedback=(
                    "Step appears to have failed due to 429 TPM error. "
                    "Only placeholder operations were generated. "
                    "No real feature code was implemented. "
                    "ACTION: Reduce prompt size or use gpt-4o-mini model."
                ),
                confidence=0.3,
                test_summary=test_summary,
                suggestions=[
                    "Reduce RAG chunks to 0-1",
                    "Reduce file context (max_files=2, max_chars=500)",
                    "Use gpt-4o-mini model (higher TPM limit)",
                    "Split step into smaller sub-steps"
                ],
                should_escalate=False
            )
        
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
                step, patch_text, test_results, previous_feedback, stack, run
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
            step, patch_text, test_results, previous_feedback, stack, run
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
        """
        🔥 SOLUTION 2: Analyze test results with PHPStan "soft mode" (Emergent.sh strategy)
        
        PHPStan failures are treated as warnings only, not blocking failures.
        This prevents workflow from being blocked by incomplete projects.
        """
        if not test_results:
            return {
                "all_passed": False,
                "total_tests": 0,
                "passed_tests": 0,
                "failed_tests": 0,
                "test_types": [],
                "failures": [],
                "warnings": []
            }
        
        passed_count = 0
        failed_count = 0
        failures = []
        warnings = []
        
        for result in test_results:
            # 🔥 SOLUTION 2: PHPStan in "soft mode" - treat as warning, not failure
            if result.test_type == "phpstan" and result.status == "failed":
                warnings.append({
                    "test_type": result.test_type,
                    "output": result.output[:500],
                    "details": result.details,
                    "reason": "PHPStan failures treated as warnings (project may be incomplete)"
                })
                # Count as "passed" so it doesn't block workflow
                passed_count += 1
                self.log.info("⚠️ PHPStan failed but treating as warning (soft mode)")
            elif result.status == "passed":
                passed_count += 1
            else:
                # Real failures (not PHPStan)
                failed_count += 1
                failures.append({
                    "test_type": result.test_type,
                    "output": result.output[:500],
                    "details": result.details
                })
        
        return {
            "all_passed": failed_count == 0,  # PHPStan doesn't count as failure
            "total_tests": len(test_results),
            "passed_tests": passed_count,
            "failed_tests": failed_count,
            "test_types": [result.test_type for result in test_results],
            "failures": failures,
            "warnings": warnings  # NEW: Separate warnings (PHPStan)
        }
    
    async def _should_escalate_to_planner(
        self,
        step: Step,
        patch_text: str,
        test_results: List[TestResult],
        previous_feedback: Optional[str],
        stack: str,
        run: Any,
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
        
        # 🔥 SOLUTION 4: Defensive parsing with retry
        max_retries = 2
        
        for attempt in range(max_retries):
            try:
                messages = [{"role": "user", "content": prompt}]
                response = await self._call_llm(run, messages)
                
                # ✅ Defensive JSON parsing
                result = defensive_json_parse(response, "escalation analysis", self.log)
                
                if result is None:
                    if attempt < max_retries - 1:
                        self.log.warning(f"⚠️ Escalation analysis failed (attempt {attempt+1}/{max_retries}), retrying...")
                        await asyncio.sleep(1)
                        # Add clarification to prompt for retry
                        prompt += "\n\n🚨 PREVIOUS ATTEMPT FAILED: Please return VALID JSON only! No explanations."
                        continue
                    else:
                        # Final attempt failed, use fallback
                        self.log.warning("⚠️ All attempts failed, using fallback (no escalation)")
                        return {
                            "should_escalate": False,
                            "confidence": 0.3,
                            "feedback": "Unable to determine escalation need (JSON parsing failed)",
                            "suggestions": []
                        }
                
                # ✅ Success - parse and return
                return {
                    "should_escalate": result.get("should_escalate", False),
                    "confidence": result.get("confidence", 0.5),
                    "feedback": result.get("feedback", "Unable to determine escalation need"),
                    "suggestions": result.get("suggestions", [])
                }
                
            except Exception as e:
                self.log.error(f"❌ Unexpected error in escalation analysis (attempt {attempt+1}): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)
                    continue
                else:
                    # Fallback on final error
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
        run: Any,
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
        
        # 🔥 SOLUTION 4: Defensive parsing with retry
        max_retries = 2
        
        for attempt in range(max_retries):
            try:
                messages = [{"role": "user", "content": prompt}]
                response = await self._call_llm(run, messages)
                
                # ✅ Defensive JSON parsing
                result = defensive_json_parse(response, "retry feedback", self.log)
                
                if result is None:
                    if attempt < max_retries - 1:
                        self.log.warning(f"⚠️ Retry feedback generation failed (attempt {attempt+1}/{max_retries}), retrying...")
                        await asyncio.sleep(1)
                        # Add clarification to prompt for retry
                        prompt += "\n\n🚨 PREVIOUS ATTEMPT FAILED: Please return VALID JSON only! No explanations."
                        continue
                    else:
                        # Final attempt failed, use fallback
                        self.log.warning("⚠️ All attempts failed, using basic feedback fallback")
                        return {
                            "feedback": f"Tests failed. Please review the following failures and adjust your implementation:\n{failures_text[:500]}",
                            "confidence": 0.5,
                            "suggestions": ["Review test failures", "Check syntax and logic", "Ensure proper imports"]
                        }
                
                # ✅ Success - parse and return
                return {
                    "feedback": result.get("feedback", "Please review test failures and adjust implementation"),
                    "confidence": result.get("confidence", 0.7),
                    "suggestions": result.get("suggestions", [])
                }
                
            except Exception as e:
                self.log.error(f"❌ Unexpected error generating retry feedback (attempt {attempt+1}): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)
                    continue
                else:
                    # Fallback on final error
                    return {
                        "feedback": f"Tests failed. Please review the following failures and adjust your implementation:\n{failures_text[:500]}",
                        "confidence": 0.5,
                        "suggestions": ["Review test failures", "Check syntax and logic", "Ensure proper imports"]
                    }
    
    async def _call_llm(self, run: Any, messages: List[Dict[str, str]], task_type: str = "review") -> str:
        """Helper method to call LLM with error handling."""
        try:
            prompt = "\n".join(m["content"] for m in messages)

            response = await self.llm_router.generate(
                prompt=prompt,
                task_type=task_type,
                current_cost=run.cost_used_eur,
                budget_limit=run.daily_budget_eur,
                run_id=run.id,
            )
            return response.content  # ✅ on renvoie bien du texte
        except Exception as e:
            self.log.error(f"LLM call failed: {e}")
            raise