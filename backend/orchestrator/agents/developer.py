"""
Developer agent implementation.

The DeveloperAgent is responsible for producing code patches given a
step description from a generated plan and the current project context.
It leverages a retrieval-augmented generation (RAG) system to provide
relevant project context, and uses the configured LLM router to
generate a unified diff between special BEGIN_PATCH and END_PATCH
markers so downstream tools can reliably apply and validate the patch.

It also integrates with a tool manager capable of validating patches
(e.g., running linters, static analyzers or test suites) before the
patch is accepted.  When validation fails, the agent can retry with
refined prompts a limited number of times.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional
import logging

from ..plan_parser import Step
from .planner import ProjectContext


@dataclass
class PatchGenerationResult:
    """Represents a generated patch and related metadata."""

    step_id: int
    stack: str
    patch_text: str
    attempts: int
    validated: bool


class PatchValidationError(Exception):
    """Raised when a patch could not be validated after retries."""


class DeveloperAgent:
    """
    Produce code patches for a given step using LLM + RAG + tool validation.

    Parameters
    ----------
    llm_router: Any
        Component responsible for calling a language model. It must expose a
        `.generate(messages)` method. If the return value is awaitable, it
        will be awaited.
    rag_system: Any
        Retrieval system used to fetch relevant project context. It should
        expose either `get_context(code_path)` or `get_relevant_chunks(code_path)`.
    tool_manager: Any
        Component providing `validate_patch(project_path, patch_text, stack)`
        (or a compatible method). It should return True/False or raise on
        unexpected errors. Validation failures should return False rather
        than raising.
    max_attempts: int
        Number of attempts when validation fails.
    logger: logging.Logger | None
        Optional logger; a default namespaced logger is used otherwise.
    """

    def __init__(
        self,
        llm_router: Any,
        rag_system: Any,
        tool_manager: Any,
        max_attempts: int = 3,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.llm_router = llm_router
        self.rag_system = rag_system
        self.tool_manager = tool_manager
        self.max_attempts = max_attempts
        self.log = logger or logging.getLogger(__name__)

    async def generate_patch(
        self,
        step: Step,
        project_context: ProjectContext,
        rag_context: Optional[List[str]] = None,
    ) -> PatchGenerationResult:
        """
        Generate a validated patch for the given step.

        The method will:
          1) Gather RAG context if not provided
          2) Build a stack-aware prompt including project file structure
          3) Ask the LLM to output a patch between BEGIN_PATCH/END_PATCH
          4) Validate the patch via `tool_manager`
          5) Retry up to `max_attempts` with refined instructions upon failure
        """
        stack = (project_context.metadata or {}).get("stack", "generic").lower()
        project_path = (project_context.metadata or {}).get("project_path")
        file_tree_snippet = (project_context.metadata or {}).get("file_tree", "")

        # 1) RAG context
        if rag_context is None and self.rag_system is not None:
            try:
                if hasattr(self.rag_system, "get_context"):
                    rag_context = await self.rag_system.get_context(project_context.code_path)
                elif hasattr(self.rag_system, "get_relevant_chunks"):
                    rag_context = await self.rag_system.get_relevant_chunks(project_context.code_path)
                else:
                    rag_context = []
            except Exception as e:
                self.log.warning(f"RAG context fetching failed: {e}")
                rag_context = []

        rag_context = rag_context or []

        last_error: Optional[str] = None
        for attempt in range(1, self.max_attempts + 1):
            # 2) Build prompt
            prompt = self._build_prompt(
                step=step,
                stack=stack,
                rag_context=rag_context,
                file_tree=file_tree_snippet,
                attempt=attempt,
                last_error=last_error,
            )

            messages = [
                {"role": "user", "content": prompt},
            ]

            # 3) LLM call
            try:
                gen = self.llm_router.generate(messages)
                if hasattr(gen, "__await__"):
                    llm_text = await gen
                else:
                    llm_text = gen  # type: ignore
            except Exception as e:
                last_error = f"LLM error: {e}"
                self.log.warning(last_error)
                # proceed to next attempt
                continue

            # Extract the patch between markers
            patch_text = self._extract_patch(llm_text)
            if not patch_text:
                last_error = "No patch found between BEGIN_PATCH/END_PATCH"
                self.log.info(f"Attempt {attempt}: {last_error}")
                continue

            # 4) Validate the patch via tool_manager if available
            is_valid = True
            if self.tool_manager is not None and hasattr(self.tool_manager, "validate_patch"):
                try:
                    is_valid = await self.tool_manager.validate_patch(
                        project_path=project_path,
                        patch_text=patch_text,
                        stack=stack,
                    )
                except Exception as e:
                    # Treat exceptions as validation failure but keep retrying
                    is_valid = False
                    last_error = f"Validation error: {e}"
                    self.log.warning(last_error)

            if is_valid:
                return PatchGenerationResult(
                    step_id=step.id,
                    stack=stack,
                    patch_text=patch_text,
                    attempts=attempt,
                    validated=True,
                )

            # Prepare next attempt
            last_error = "Patch validation failed"
            self.log.info(f"Attempt {attempt} failed validation; retrying…")

        # All attempts exhausted
        raise PatchValidationError(
            f"Could not produce a valid patch for step {step.id} after {self.max_attempts} attempts. Last error: {last_error}"
        )

    # ---------- Prompt building helpers ----------

    def _build_prompt(
        self,
        *,
        step: Step,
        stack: str,
        rag_context: List[str],
        file_tree: str,
        attempt: int,
        last_error: Optional[str],
    ) -> str:
        """Create a contextual, stack-aware prompt for the LLM."""
        guidelines = self._stack_guidelines(stack)
        rag_block = "\n".join(rag_context[:8]) if rag_context else "(no additional context)"
        error_hint = f"Previous attempt failed: {last_error}." if last_error else ""

        file_tree_block = (
            f"Existing project structure (partial):\n{file_tree.strip()}\n\n" if file_tree else ""
        )

        return (
            "You are a senior software developer. Implement the following step as a precise code diff.\n\n"
            f"Step #{step.id}: {step.description}\n\n"
            f"Target stack: {stack}\n\n"
            f"Context from RAG (may include code excerpts, constraints):\n{rag_block}\n\n"
            f"{file_tree_block}"
            f"Coding standards and constraints for this stack:\n{guidelines}\n\n"
            f"{error_hint}\n"
            "Output a unified diff that can be applied with `git apply`.\n"
            "Wrap ONLY the diff between the exact markers below:\n"
            "BEGIN_PATCH\n"
            "<git unified diff here>\n"
            "END_PATCH\n"
        )

    def _stack_guidelines(self, stack: str) -> str:
        stack = (stack or "").lower()
        if stack == "laravel":
            return (
                "- PHP 8+, PSR-12, Laravel conventions.\n"
                "- Prefer dependency injection, FormRequests, Eloquent models.\n"
                "- Update routes, controllers, tests (Pest).\n"
                "- Provide migrations/factories when schema changes."
            )
        if stack == "react":
            return (
                "- React 18, functional components, hooks.\n"
                "- TypeScript preferred, Vite or CRA layout respected.\n"
                "- Unit tests with Jest/RTL when altering logic."
            )
        if stack == "vue":
            return (
                "- Vue 3 + Vite, single-file components (.vue).\n"
                "- Composition API.\n"
                "- Unit tests with Vitest where applicable."
            )
        if stack == "python":
            return (
                "- Python 3.10+, PEP8/Flake8, type hints where useful.\n"
                "- Pytest tests for new behavior; keep functions small and pure."
            )
        if stack == "node":
            return (
                "- Node 18+, ESM or CommonJS consistently.\n"
                "- Add Jest tests for business logic."
            )
        return (
            "- Follow idiomatic patterns for the language.\n"
            "- Include minimal tests or usage examples when changing logic."
        )

    def _extract_patch(self, text: str) -> str | None:
        """Return the diff between BEGIN_PATCH and END_PATCH or None.

        If the model returns a plain diff without markers but containing
        unified diff hunks (e.g., lines with "@@"), we return it as-is.
        """
        if not text:
            return None
        start = text.find("BEGIN_PATCH")
        end = text.find("END_PATCH")
        if start != -1 and end != -1 and start < end:
            body = text[start + len("BEGIN_PATCH"):end].strip()
            return body if body else None
        # Fallback: accept raw unified diff
        if "@@" in text or text.strip().startswith("diff --git"):
            return text.strip()
        return None
