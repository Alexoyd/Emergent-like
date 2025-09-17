from fastapi import FastAPI, APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import json
import asyncio
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Literal
import uuid
from datetime import datetime, timezone
from dataclasses import dataclass
from enum import Enum
import subprocess
import tempfile
import shutil
import git
from contextlib import asynccontextmanager

# Import AI orchestrator components
from orchestrator.llm_router import LLMRouter
from orchestrator.tools import ToolManager
from orchestrator.state_manager import StateManager
from orchestrator.rag_system import RAGSystem

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Initialize orchestrator components
llm_router = LLMRouter()
tool_manager = ToolManager()
state_manager = StateManager(db)
rag_system = RAGSystem()

# Create the main app without a prefix
app = FastAPI(title="AI Agent Orchestrator", version="1.0.0")

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Models
class RunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"

class RunCreate(BaseModel):
    goal: str = Field(..., min_length=10, max_length=2000, description="Detailed description of what the AI should accomplish")
    project_path: Optional[str] = Field(None, description="Optional path to existing project")
    stack: str = Field("laravel", pattern="^(laravel|react|vue|python|node)$", description="Technology stack to use")
    max_steps: int = Field(20, ge=1, le=50, description="Maximum number of steps to execute")
    max_retries_per_step: int = Field(2, ge=0, le=5, description="Maximum retries per step")
    daily_budget_eur: float = Field(5.0, ge=0.1, le=100.0, description="Daily budget limit in EUR")

class Run(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    goal: str
    project_path: Optional[str] = None
    stack: str = "laravel"
    status: RunStatus = RunStatus.PENDING
    current_step: int = 0
    max_steps: int = 20
    max_retries_per_step: int = 2
    daily_budget_eur: float = 5.0
    cost_used_eur: float = 0.0
    steps: List[Dict[str, Any]] = []
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    logs: List[Dict[str, Any]] = []

class Step(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    run_id: str
    step_number: int
    description: str
    status: StepStatus = StepStatus.PENDING
    model_used: Optional[str] = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_eur: float = 0.0
    retries: int = 0
    max_retries: int = 2
    output: Optional[str] = None
    error: Optional[str] = None
    patch: Optional[str] = None
    tests_passed: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class FileOperation(BaseModel):
    operation: Literal["read", "write"]
    file_path: str
    content: Optional[str] = None

class TestResult(BaseModel):
    test_type: str
    status: Literal["passed", "failed"]
    output: str
    details: Optional[Dict[str, Any]] = None

# Routes

@api_router.get("/")
async def root():
    return {"message": "AI Agent Orchestrator API v1.0.0", "status": "running"}

@api_router.post("/runs", response_model=Run)
async def create_run(run_data: RunCreate, background_tasks: BackgroundTasks):
    """Create a new AI agent run"""
    try:
        # Create run record
        run = Run(**run_data.dict())
        
        # Save to database
        await db.runs.insert_one(run.dict())
        
        # Start orchestration in background
        background_tasks.add_task(execute_run, run.id)
        
        return run
    except Exception as e:
        logging.error(f"Error creating run: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/runs/{run_id}", response_model=Run)
async def get_run(run_id: str):
    """Get run details"""
    try:
        run_data = await db.runs.find_one({"id": run_id})
        if not run_data:
            raise HTTPException(status_code=404, detail="Run not found")
        return Run(**run_data)
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error getting run: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/runs", response_model=List[Run])
async def list_runs(limit: int = 10, offset: int = 0):
    """List all runs"""
    try:
        runs = await db.runs.find().skip(offset).limit(limit).sort("created_at", -1).to_list(length=None)
        return [Run(**run) for run in runs]
    except Exception as e:
        logging.error(f"Error listing runs: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/runs/{run_id}/cancel")
async def cancel_run(run_id: str):
    """Cancel a running run"""
    try:
        await state_manager.cancel_run(run_id)
        return {"message": "Run cancelled successfully"}
    except Exception as e:
        logging.error(f"Error cancelling run: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/runs/{run_id}/retry-step")
async def retry_step(run_id: str, step_number: int, background_tasks: BackgroundTasks):
    """Retry a specific step"""
    try:
        # Mark step for retry
        await state_manager.retry_step(run_id, step_number)
        
        # Continue execution in background
        background_tasks.add_task(execute_run, run_id, from_step=step_number)
        
        return {"message": "Step retry initiated"}
    except Exception as e:
        logging.error(f"Error retrying step: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/files/read")
async def read_files(operations: List[FileOperation]):
    """Read multiple files"""
    try:
        results = []
        for op in operations:
            if op.operation != "read":
                continue
            content = await tool_manager.read_file(op.file_path)
            results.append({
                "file_path": op.file_path,
                "content": content,
                "success": True
            })
        return {"results": results}
    except Exception as e:
        logging.error(f"Error reading files: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/files/write")
async def write_files(operations: List[FileOperation]):
    """Write multiple files"""
    try:
        results = []
        for op in operations:
            if op.operation != "write" or not op.content:
                continue
            success = await tool_manager.write_file(op.file_path, op.content)
            results.append({
                "file_path": op.file_path,
                "success": success
            })
        return {"results": results}
    except Exception as e:
        logging.error(f"Error writing files: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/test/{project_id}")
async def run_tests(project_id: str, test_types: List[str] = None):
    """Run tests for a project"""
    try:
        if not test_types:
            test_types = ["pest", "phpstan", "pint", "jest"]
        
        results = []
        for test_type in test_types:
            result = await tool_manager.run_test(project_id, test_type)
            results.append(result)
        
        return {"results": results}
    except Exception as e:
        logging.error(f"Error running tests: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/runs/{run_id}/stream")
async def stream_run_logs(run_id: str):
    """Stream run logs in real-time"""
    async def generate():
        last_log_count = 0
        while True:
            try:
                run_data = await db.runs.find_one({"id": run_id})
                if not run_data:
                    break
                
                run = Run(**run_data)
                
                # Send new logs
                if len(run.logs) > last_log_count:
                    new_logs = run.logs[last_log_count:]
                    for log in new_logs:
                        yield f"data: {json.dumps(log)}\n\n"
                    last_log_count = len(run.logs)
                
                # Send status update
                yield f"data: {json.dumps({'type': 'status', 'status': run.status, 'current_step': run.current_step})}\n\n"
                
                # Break if run is completed
                if run.status in [RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED]:
                    break
                
                await asyncio.sleep(1)
            except Exception as e:
                logging.error(f"Error streaming logs: {e}")
                break
    
    return StreamingResponse(generate(), media_type="text/plain")

# Core orchestration logic

async def execute_run(run_id: str, from_step: int = 0):
    """Execute a run with AI orchestration"""
    try:
        # Get run details
        run_data = await db.runs.find_one({"id": run_id})
        if not run_data:
            return
        
        run = Run(**run_data)
        
        # Update status to running
        await state_manager.update_run_status(run_id, RunStatus.RUNNING)
        
        # Initialize RAG system with project context
        if run.project_path:
            await rag_system.index_project(run.project_path)
        
        # Generate initial plan
        if from_step == 0:
            plan = await generate_plan(run)
            await state_manager.add_log(run_id, {"type": "plan", "content": plan})
        
        # Execute steps
        current_step = from_step
        while current_step < run.max_steps:
            try:
                # Check if run was cancelled
                run_data = await db.runs.find_one({"id": run_id})
                if not run_data or Run(**run_data).status == RunStatus.CANCELLED:
                    break
                
                # Execute step
                step_result = await execute_step(run_id, current_step)
                
                # Check if step failed and needs retry
                if not step_result.tests_passed and step_result.retries < step_result.max_retries:
                    # Retry with higher model
                    await retry_step_with_escalation(run_id, current_step, step_result.retries + 1)
                    continue
                elif not step_result.tests_passed:
                    # Max retries reached, fail the run
                    await state_manager.update_run_status(run_id, RunStatus.FAILED)
                    break
                
                current_step += 1
                
                # Check budget limit
                run_data = await db.runs.find_one({"id": run_id})
                if run_data and Run(**run_data).cost_used_eur >= run.daily_budget_eur:
                    await state_manager.add_log(run_id, {"type": "warning", "content": "Daily budget limit reached"})
                    break
                
            except Exception as e:
                logging.error(f"Error executing step {current_step}: {e}")
                await state_manager.add_log(run_id, {"type": "error", "content": f"Step {current_step} failed: {str(e)}"})
                break
        
        # Mark as completed if all steps successful
        if current_step >= run.max_steps or current_step == 0:
            await state_manager.update_run_status(run_id, RunStatus.COMPLETED)
        
    except Exception as e:
        logging.error(f"Error executing run {run_id}: {e}")
        await state_manager.update_run_status(run_id, RunStatus.FAILED)

async def generate_plan(run: Run) -> str:
    """Generate execution plan using LLM"""
    try:
        # Get relevant context from RAG
        context = ""
        if run.project_path:
            context = await rag_system.get_relevant_context(run.goal)
        
        # Create planning prompt
        prompt = f"""
You are an AI coding agent. Create a step-by-step plan to achieve this goal:

GOAL: {run.goal}
PROJECT: {run.stack} project at {run.project_path or 'new project'}
MAX_STEPS: {run.max_steps}

CONTEXT:
{context}

Create a detailed plan with specific, actionable steps. Each step should:
1. Be testable and verifiable
2. Produce minimal, focused code changes
3. Include specific files to modify
4. Define success criteria

Format as numbered list with brief descriptions.
"""
        
        response = await llm_router.generate(prompt, "planning", run.cost_used_eur, run.daily_budget_eur)
        return response.content
        
    except Exception as e:
        logging.error(f"Error generating plan: {e}")
        return f"Error generating plan: {str(e)}"

async def execute_step(run_id: str, step_number: int) -> Step:
    """Execute a single step"""
    try:
        # Get run details
        run_data = await db.runs.find_one({"id": run_id})
        run = Run(**run_data)
        
        # Create step record
        step = Step(
            run_id=run_id,
            step_number=step_number,
            description=f"Step {step_number + 1}",
            max_retries=run.max_retries_per_step
        )
        
        # Update step to running
        step.status = StepStatus.RUNNING
        await db.steps.insert_one(step.dict())
        
        # Generate step prompt
        context = await rag_system.get_relevant_context(run.goal) if run.project_path else ""
        
        prompt = f"""
You are an AI coding agent executing step {step_number + 1} of a plan.

ORIGINAL GOAL: {run.goal}
PROJECT: {run.stack} project at {run.project_path or 'new project'}
STEP: {step_number + 1}/{run.max_steps}

CONTEXT:
{context}

PREVIOUS STEPS:
{await get_previous_steps_summary(run_id, step_number)}

Generate code changes as a unified diff patch. Output format:

BEGIN_PATCH
<unified diff or file content changes - MAX 2 files>
END_PATCH

CHECKLIST
- Tests Pest: OK/KO
- PHPStan: OK/KO  
- Pint: OK/KO
- Jest/Playwright: OK/KO
- Comments: <brief summary of changes and reasoning>

Be specific, focused, and ensure changes are minimal and testable.
"""
        
        # Generate response using LLM router
        response = await llm_router.generate(prompt, "coding", run.cost_used_eur, run.daily_budget_eur)
        
        # Parse patch from response
        patch = extract_patch(response.content)
        
        # Apply patch
        if patch:
            await tool_manager.apply_patch(patch, run.project_path)
            step.patch = patch
        
        # Run tests
        test_results = await run_comprehensive_tests(run.project_path, run.stack)
        step.tests_passed = all(result.status == "passed" for result in test_results)
        
        # Update step with results
        step.status = StepStatus.COMPLETED if step.tests_passed else StepStatus.FAILED
        step.output = response.content
        step.model_used = response.model
        step.prompt_tokens = response.prompt_tokens
        step.completion_tokens = response.completion_tokens
        step.cost_eur = response.cost_eur
        
        # Update database
        await db.steps.replace_one({"id": step.id}, step.dict())
        
        # Update run cost
        await state_manager.add_cost(run_id, response.cost_eur)
        
        return step
        
    except Exception as e:
        logging.error(f"Error executing step: {e}")
        step.status = StepStatus.FAILED
        step.error = str(e)
        await db.steps.replace_one({"id": step.id}, step.dict())
        return step

async def retry_step_with_escalation(run_id: str, step_number: int, retry_count: int):
    """Retry step with model escalation"""
    try:
        # Get original step
        step_data = await db.steps.find_one({"run_id": run_id, "step_number": step_number})
        if not step_data:
            return
        
        step = Step(**step_data)
        step.retries = retry_count
        step.status = StepStatus.RETRYING
        
        # Force escalation for retry
        llm_router.force_escalation = True
        
        # Re-execute step
        result = await execute_step(run_id, step_number)
        
        # Reset escalation
        llm_router.force_escalation = False
        
        return result
        
    except Exception as e:
        logging.error(f"Error retrying step: {e}")

def extract_patch(content: str) -> Optional[str]:
    """Extract patch from LLM response"""
    try:
        start_marker = "BEGIN_PATCH"
        end_marker = "END_PATCH"
        
        start_idx = content.find(start_marker)
        end_idx = content.find(end_marker)
        
        if start_idx != -1 and end_idx != -1:
            patch = content[start_idx + len(start_marker):end_idx].strip()
            return patch
        
        return None
    except Exception as e:
        logging.error(f"Error extracting patch: {e}")
        return None

async def get_previous_steps_summary(run_id: str, current_step: int) -> str:
    """Get summary of previous steps"""
    try:
        steps = await db.steps.find({"run_id": run_id, "step_number": {"$lt": current_step}}).sort("step_number", 1).to_list(length=None)
        
        summary = []
        for step_data in steps:
            step = Step(**step_data)
            summary.append(f"Step {step.step_number + 1}: {step.description} - {step.status}")
        
        return "\n".join(summary)
    except Exception as e:
        logging.error(f"Error getting previous steps: {e}")
        return ""

async def run_comprehensive_tests(project_path: Optional[str], stack: str) -> List[TestResult]:
    """Run comprehensive tests based on stack"""
    try:
        results = []
        
        if stack == "laravel":
            # Laravel tests
            results.append(await tool_manager.run_test(project_path, "pest"))
            results.append(await tool_manager.run_test(project_path, "phpstan"))
            results.append(await tool_manager.run_test(project_path, "pint"))
        elif stack in ["react", "node"]:
            # JavaScript tests
            results.append(await tool_manager.run_test(project_path, "jest"))
            results.append(await tool_manager.run_test(project_path, "eslint"))
        
        return results
    except Exception as e:
        logging.error(f"Error running tests: {e}")
        return []

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()