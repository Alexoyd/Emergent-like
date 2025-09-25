"""
Planner agent implementation.

The PlannerAgent is responsible for generating a high‑level plan given
an initial task description and the current project context.  It
leverages a retrieval augmented generation (RAG) system to provide
relevant context from the project's codebase and passes a prompt to
the LLM router for generation.  The returned plan text is then
parsed into a structured list of steps via :class:`PlanParser`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Any

from ..plan_parser import PlanParser, Step, PlanParsingError


@dataclass
class ProjectContext:
    """Encapsulate context information about a project for planning.

    This simple dataclass can be extended to include more metadata such as
    project ID, code path, prior runs, etc.  The planner uses the RAG
    system to obtain relevant documentation and code snippets.
    """
    # Path or identifier for the project's code.  Optional if rag_system
    # does not require a path.
    code_path: str | None = None
    # Additional arbitrary metadata
    metadata: dict[str, Any] | None = None

@dataclass
class PlanGenerationResult:
    """Result of a call to :meth:`PlannerAgent.generate_plan`."""
    plan_text: str
    steps: List[Step]
    context: List[str]


class PlannerAgent:
    """Generate structured plans from task descriptions and project context."""

    def __init__(self, llm_router: Any, rag_system: Any) -> None:
        """Initialise the planner with an LLM router and a RAG system.

        :param llm_router: An object capable of producing completions
            given messages (e.g., orchestrator.llm_router.LLMRouter).
        :param rag_system: A retrieval system that can provide contextual
            documents given a project code path.
        """
        self.llm_router = llm_router
        self.rag_system = rag_system
        self.plan_parser = PlanParser()

    async def generate_plan(self, task: str, project_context: ProjectContext) -> PlanGenerationResult:
        """Generate a plan for the given task and project context.

        This method retrieves relevant context via the RAG system,
        constructs a prompt instructing the language model to output a
        structured plan (e.g. numbered list with descriptions and
        optional metadata), invokes the LLM router to obtain a plan
        string, parses the plan into structured steps and returns the
        result.  If parsing fails, an error is raised.

        :param task: A natural language description of the desired outcome.
        :param project_context: Information about the current project.
        :raises PlanParsingError: If the generated plan cannot be parsed.
        :return: A :class:`PlanGenerationResult` containing the plan text,
            the parsed steps and the context used.
        """
        # Retrieve contextual information from the RAG system.  The RAG
        # system is expected to implement a method `get_relevant_chunks`
        # or similar; we handle missing methods gracefully.
        context_docs: List[str] = []
        if self.rag_system is not None:
            try:
                # Attempt to call a generic method to fetch context
                if hasattr(self.rag_system, "get_context"):
                    context_docs = await self.rag_system.get_context(
                        project_context.code_path
                    )
                elif hasattr(self.rag_system, "get_relevant_chunks"):
                    context_docs = await self.rag_system.get_relevant_chunks(
                        project_context.code_path
                    )
            except Exception as e:
                # Log but proceed with empty context
                import logging

                logging.warning(f"Failed to retrieve RAG context: {e}")

        # Build prompt instructing the model to produce a structured plan
        prompt_parts = []
        prompt_parts.append(
            "You are a planning agent tasked with decomposing a high level task into a sequence of clear, ordered steps."
        )
        if context_docs:
            prompt_parts.append(
                "The following context from the project may be relevant:\n"
                + "\n".join(context_docs[:5])
            )
        prompt_parts.append(
            "Please produce a numbered plan where each step begins with the step number followed by a description.\n"
            "Include additional metadata when available, such as files involved, commands to run, durations and dependencies."
        )
        prompt_parts.append(f"Task: {task.strip()}")
        prompt_parts.append(
            "Return the plan in plain text. Do not wrap it in JSON or any other format."
        )
        prompt = "\n\n".join(prompt_parts)

        # Construct a conversation payload for the LLM router.  The router
        # expects an array of message dicts with roles and content.  We
        # provide a single user message containing the prompt.  The router
        # internally handles escalations between model tiers.
        messages = [
            {"role": "user", "content": prompt},
        ]

        # Request a plan from the LLM router.  The router may be
        # asynchronous or synchronous depending on implementation.  We
        # attempt to await it if it is a coroutine.
        try:
            plan_text: str
            result = self.llm_router.generate(messages)
            if hasattr(result, "__await__"):
                # If the result is awaitable, await it to get the final text
                plan_text = await result
            else:
                plan_text = result  # type: ignore[assignment]
        except Exception as e:
            raise PlanParsingError(f"LLM generation failed: {e}") from e

        # Parse the plan into structured steps
        try:
            steps = self.plan_parser.parse_plan(plan_text)
        except PlanParsingError:
            # Propagate parsing errors
            raise
        except Exception as e:
            raise PlanParsingError(f"Unexpected error parsing plan: {e}") from e

        if not steps:
            raise PlanParsingError("Generated plan is empty")

        return PlanGenerationResult(plan_text=plan_text, steps=steps, context=context_docs)
