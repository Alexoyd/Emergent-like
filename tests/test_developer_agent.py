import pytest
import asyncio

from backend.orchestrator.agents.developer import (
    DeveloperAgent,
    PatchGenerationResult,
    PatchValidationError,
)
from backend.orchestrator.agents.planner import ProjectContext
from backend.orchestrator.plan_parser import Step, ActionType


class DummyToolManager:
    """A simple tool manager that validates patches based on content."""

    def __init__(self):
        self.calls = []

    async def validate_patch(self, project_path, patch_text, stack):
        self.calls.append({
            "project_path": project_path,
            "patch_text": patch_text,
            "stack": stack,
        })
        # Simulate validation rules
        if "INVALID" in patch_text:
            return False
        if "RAISE" in patch_text:
            raise RuntimeError("validator exploded")
        return True


class DummyLLMRouter:
    """A synchronous dummy LLM router returning scripted responses."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.last_prompt = None

    def generate(self, messages):
        # store prompt for assertions
        self.last_prompt = messages[0]["content"]
        if not self.responses:
            return "BEGIN_PATCH\n\nEND_PATCH"  # empty
        return self.responses.pop(0)


class DummyAsyncLLMRouter:
    """An async LLM router."""

    def __init__(self, response):
        self.response = response

    def generate(self, messages):
        async def _inner():
            await asyncio.sleep(0)
            return self.response
        return _inner()


@pytest.mark.asyncio
async def test_generate_patch_success():
    llm = DummyLLMRouter([
        """Some text
BEGIN_PATCH
diff --git a/app.py b/app.py
@@ -1,2 +1,3 @@
-print('hi')
+print('hello')
END_PATCH""",
    ])
    tool = DummyToolManager()
    agent = DeveloperAgent(llm_router=llm, rag_system=None, tool_manager=tool)

    step = Step(id=1, description="Modify greeting", type_action=ActionType.MODIFY_FILE)
    ctx = ProjectContext(code_path=None, metadata={"stack": "python", "project_path": "/tmp/proj"})

    res = await agent.generate_patch(step, ctx)
    assert isinstance(res, PatchGenerationResult)
    assert res.validated is True
    assert "diff --git" in res.patch_text
    assert res.attempts == 1


@pytest.mark.asyncio
async def test_generate_patch_retry_on_validation_failure():
    llm = DummyLLMRouter([
        "BEGIN_PATCH\nINVALID DIFF\nEND_PATCH",  # first attempt invalid
        "BEGIN_PATCH\ndiff --git a/x b/x\n@@ -1 +1 @@\n-1\n+2\nEND_PATCH",  # second attempt valid
    ])
    tool = DummyToolManager()
    agent = DeveloperAgent(llm_router=llm, rag_system=None, tool_manager=tool)

    step = Step(id=2, description="Change value", type_action=ActionType.MODIFY_FILE)
    ctx = ProjectContext(code_path=None, metadata={"stack": "node"})

    res = await agent.generate_patch(step, ctx)
    assert res.attempts == 2
    assert res.validated is True


@pytest.mark.asyncio
async def test_generate_patch_raises_after_max_attempts():
    llm = DummyLLMRouter([
        "BEGIN_PATCH\nINVALID\nEND_PATCH",
        "BEGIN_PATCH\nINVALID\nEND_PATCH",
        "BEGIN_PATCH\nINVALID\nEND_PATCH",
    ])
    tool = DummyToolManager()
    agent = DeveloperAgent(llm_router=llm, rag_system=None, tool_manager=tool, max_attempts=3)

    step = Step(id=3, description="Failing step", type_action=ActionType.MODIFY_FILE)
    ctx = ProjectContext(code_path=None, metadata={"stack": "laravel"})

    with pytest.raises(PatchValidationError):
        await agent.generate_patch(step, ctx)


@pytest.mark.asyncio
async def test_prompt_contains_stack_guidelines():
    # We want to assert that guidelines for a stack are present in the prompt.
    # For Laravel we included the keyword PSR-12 in guidelines.
    llm = DummyLLMRouter([
        "BEGIN_PATCH\ndiff --git a/app.php b/app.php\n@@ -1 +1 @@\n-1\n+2\nEND_PATCH",
    ])
    tool = DummyToolManager()
    agent = DeveloperAgent(llm_router=llm, rag_system=None, tool_manager=tool)

    step = Step(id=4, description="Implement controller", type_action=ActionType.CREATE_FILE)
    ctx = ProjectContext(code_path=None, metadata={"stack": "laravel"})

    await agent.generate_patch(step, ctx)
    assert "PSR-12" in llm.last_prompt


@pytest.mark.asyncio
async def test_extract_patch_without_markers():
    # Router returns a raw diff without BEGIN/END markers
    raw = "diff --git a/a b/a\n@@ -1 +1 @@\n-1\n+2\n"
    llm = DummyLLMRouter([raw])
    tool = DummyToolManager()
    agent = DeveloperAgent(llm_router=llm, rag_system=None, tool_manager=tool)

    step = Step(id=5, description="Raw diff", type_action=ActionType.MODIFY_FILE)
    ctx = ProjectContext(code_path=None, metadata={"stack": "vue"})

    res = await agent.generate_patch(step, ctx)
    assert res.validated is True
    assert res.patch_text.strip().startswith("diff --git")


@pytest.mark.asyncio
async def test_validation_exception_triggers_retry():
    # First, validator raises; second time succeeds
    llm = DummyLLMRouter([
        "BEGIN_PATCH\nRAISE\nEND_PATCH",
        "BEGIN_PATCH\ndiff --git a/a b/a\n@@ -1 +1 @@\n-1\n+2\nEND_PATCH",
    ])
    tool = DummyToolManager()
    agent = DeveloperAgent(llm_router=llm, rag_system=None, tool_manager=tool)

    step = Step(id=6, description="Retry on exception", type_action=ActionType.MODIFY_FILE)
    ctx = ProjectContext(code_path=None, metadata={"stack": "python"})

    res = await agent.generate_patch(step, ctx)
    assert res.attempts == 2


@pytest.mark.asyncio
async def test_llm_exception_handled():
    class ExplodingLLM:
        def __init__(self):
            self.calls = 0
        def generate(self, messages):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("temporary LLM outage")
            return "BEGIN_PATCH\ndiff --git a/a b/a\n@@ -1 +1 @@\n-1\n+2\nEND_PATCH"

    tool = DummyToolManager()
    agent = DeveloperAgent(llm_router=ExplodingLLM(), rag_system=None, tool_manager=tool)

    step = Step(id=7, description="LLM hiccup", type_action=ActionType.MODIFY_FILE)
    ctx = ProjectContext(code_path=None, metadata={"stack": "generic"})

    res = await agent.generate_patch(step, ctx)
    assert isinstance(res, PatchGenerationResult)
