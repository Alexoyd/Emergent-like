import pytest
import asyncio

from backend.orchestrator.agents.planner import (
    PlannerAgent,
    ProjectContext,
    PlanGenerationResult,
)
from backend.orchestrator.plan_parser import PlanParsingError


class DummyRAG:
    """A simple asynchronous RAG system returning static context."""

    async def get_context(self, code_path):
        return ["Existing code snippet", "Another context snippet"]


class DummyLLMRouter:
    """A synchronous dummy LLM router returning a simple plan."""

    def generate(self, messages):
        # Always return a two‑step plan irrespective of the prompt
        return "1. Set up environment\n2. Implement feature"


class DummyAsyncLLMRouter:
    """An asynchronous dummy LLM router returning a simple plan."""

    def generate(self, messages):
        async def _inner():
            await asyncio.sleep(0)  # simulate async
            return "1. Async setup\n2. Async build"
        return _inner()


@pytest.mark.asyncio
async def test_generate_plan_basic():
    rag = DummyRAG()
    llm = DummyLLMRouter()
    agent = PlannerAgent(llm_router=llm, rag_system=rag)
    ctx = ProjectContext(code_path="/fake/path")
    result = await agent.generate_plan("Implement new feature", ctx)
    assert isinstance(result, PlanGenerationResult)
    assert len(result.steps) == 2
    assert result.steps[0].description.lower().startswith("set up")
    # RAG context should be included
    assert result.context


@pytest.mark.asyncio
async def test_generate_plan_async_llm():
    rag = DummyRAG()
    llm = DummyAsyncLLMRouter()
    agent = PlannerAgent(llm_router=llm, rag_system=rag)
    ctx = ProjectContext(code_path="/fake/path")
    result = await agent.generate_plan("Async plan test", ctx)
    assert isinstance(result, PlanGenerationResult)
    assert len(result.steps) == 2
    assert result.steps[0].description.lower().startswith("async setup")


@pytest.mark.asyncio
async def test_generate_plan_parsing_error():
    rag = DummyRAG()

    class BadLLMRouter:
        def generate(self, messages):
            return "This plan cannot be parsed into steps"

    agent = PlannerAgent(llm_router=BadLLMRouter(), rag_system=rag)
    ctx = ProjectContext(code_path="/fake/path")
    with pytest.raises(PlanParsingError):
        await agent.generate_plan("Unstructured task", ctx)
