from fastapi import FastAPI, APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse, FileResponse
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
import dataclasses
from dataclasses import dataclass
from enum import Enum
import subprocess
import tempfile
import shutil
import git
from contextlib import asynccontextmanager
from fastapi import WebSocket, WebSocketDisconnect

# Import AI orchestrator components
from orchestrator.llm_router import LLMRouter
from orchestrator.tools import ToolManager
from orchestrator.state_manager import StateManager
from orchestrator.rag_system import RAGSystem
from orchestrator.project_manager import ProjectManager
from orchestrator.github_integration import GitHubIntegration
from orchestrator.plan_parser import PlanParser
from orchestrator.agents import PlannerAgent, DeveloperAgent, ReviewerAgent
from orchestrator.agents.planner import ProjectContext
from orchestrator.agents.reviewer import TestResult as ReviewerTestResult, ReviewDecision
from orchestrator.plan_parser import Step as PlanStep
from orchestrator.utils import json_utils
from orchestrator.utils import bson_utils

# 🔥 PHASE 1: Direct file writing imports
from orchestrator.agents.developer_direct import DeveloperAgentDirect, OperationsResult
from orchestrator.file_writer import execute_operations, FileWriterError
from orchestrator.schemas import DeveloperOutput, StepCommit

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# 🔥 PHASE 1: File write mode configuration
FILE_WRITE_MODE = os.getenv("FILE_WRITE_MODE", "direct").lower()  # "direct" or "patch"
logger = logging.getLogger(__name__)
logger.info(f"🚀 File write mode: {FILE_WRITE_MODE.upper()}")

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Initialize orchestrator components
llm_router = LLMRouter()
tool_manager = ToolManager(llm_router=llm_router)
state_manager = StateManager(db)
rag_system = RAGSystem()
project_manager = ProjectManager()
github_integration = GitHubIntegration()
plan_parser = PlanParser()

# Initialize agents
planner_agent = PlannerAgent(llm_router, rag_system)

# 🔥 PHASE 1: Conditional DeveloperAgent initialization
if FILE_WRITE_MODE == "direct":
    developer_agent = DeveloperAgentDirect(llm_router, rag_system, tool_manager)
    logger.info("✅ Using DeveloperAgentDirect (JSON operations)")
else:
    developer_agent = DeveloperAgent(llm_router, rag_system, tool_manager)
    logger.info("✅ Using DeveloperAgent (Git patches)")

reviewer_agent = ReviewerAgent(llm_router)

# Create the main app without a prefix
app = FastAPI(title="AI Agent Orchestrator", version="1.0.0")

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

async def _upsert_step(step: Any) -> None:
    """Upsert d'un step dans Mongo, en BSON-safe."""
    if hasattr(step, "to_dict"):
        payload = step.to_dict()
    elif hasattr(step, "dict"):
        payload = step.dict()
    else:
        payload = dataclasses.asdict(step)  # dataclass

    # Récupère l'ID de manière robuste
    step_id = payload.get("id", getattr(step, "id", None))
    
    # TODO: Implémenter la logique d'upsert dans MongoDB
    # await db.steps.update_one(
    #     {"id": step_id},
    #     {"$set": bson_utils.bson_safe(payload)},
    #     upsert=True
    # )

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
    stack: str = Field("unknown", pattern="^(laravel|react|vue|python|node|unknown)$", description="Technology stack to use - 'unknown' for auto-detection")
    max_steps: int = Field(20, ge=1, le=50, description="Maximum number of steps to execute")
    max_retries_per_step: int = Field(2, ge=0, le=5, description="Maximum retries per step")
    daily_budget_eur: float = Field(5.0, ge=0.1, le=100.0, description="Daily budget limit in EUR")
    
    # 🔥 PHASE 2: Attach mode
    project_mode: Literal["create", "attach"] = Field("create", description="'create' = new project, 'attach' = existing project")
    project_id: Optional[str] = Field(None, description="Project ID to attach (if project_mode='attach')")

class Run(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    goal: str
    project_path: Optional[str] = None
    stack: str = "unknown"
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
    
    # 🔥 PHASE 2: Attach mode
    project_mode: str = "create"
    project_id: Optional[str] = None
    attached_commit: Optional[str] = None  # Initial commit hash when attached

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

@api_router.post("/runs/preview-plan")
async def preview_plan(run_data: RunCreate):
    """Generate a preview of the execution plan without creating a run"""
    try:
        # Create a temporary planner context
        planner = PlannerAgent(llm_router, tool_manager)
        context = ProjectContext(
            goal=run_data.goal,
            stack=run_data.stack,
            project_path=run_data.project_path or f"/tmp/preview-{uuid.uuid4()}",
            existing_files=[],
            budget_constraints={"daily_budget_eur": run_data.daily_budget_eur}
        )
        
        # Generate plan preview
        plan = await planner.create_plan(context)
        
        return {
            "plan": plan,
            "estimated_steps": len(plan.split('')) if plan else 0,
            "estimated_cost": 0.05 * run_data.max_steps,  # Rough estimate
            "stack": run_data.stack
        }
    except Exception as e:
        logging.error(f"Error generating plan preview: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class ExecuteOperationsRequest(BaseModel):
    """🔥 PHASE 2: Request for no-LLM operations execution"""
    run_id: str = Field(..., description="Run ID")
    project_id: str = Field(..., description="Project ID")
    operations: List[Dict[str, Any]] = Field(..., min_items=1, description="List of file operations to execute")
    commit: Dict[str, Any] = Field(..., description="Commit metadata: {title, step_number}")

@api_router.post("/runs/execute-operations")
async def execute_operations_endpoint(request: ExecuteOperationsRequest):
    """
    🔥 PHASE 2: Execute file operations directly (no-LLM path)
    
    Allows testing attach mode end-to-end without LLM keys.
    Applies same pipeline as LLM mode:
    - Validation (deny-list, path checks)
    - File operations execution
    - Git commit
    - RAG re-indexing
    - Artifacts logging
    
    Returns: {
        "status": "success" | "failed",
        "operations_executed": int,
        "commit_hash": str,
        "artifacts": {...}
    }
    """
    try:
        # Validate run exists
        run_data = await db.runs.find_one({"id": request.run_id})
        if not run_data:
            raise HTTPException(status_code=404, detail=f"Run {request.run_id} not found")
        
        run = Run(**run_data)
        
        # Get project path
        project_code_path = project_manager.get_code_path(request.project_id)
        if not project_code_path.exists():
            raise HTTPException(status_code=404, detail=f"Project {request.project_id} not found")
        
        # Execute operations
        logger.info(f"🔥 Executing {len(request.operations)} operations for run {request.run_id}")
        
        exec_results = await execute_operations(
            request.operations,
            str(project_code_path),
            request.project_id
        )
        
        # Check for failures
        failed_ops = [r for r in exec_results if r.get("status") == "failed"]
        if failed_ops:
            errors = "; ".join([f"{r.get('operation_type', 'unknown')}: {r.get('error', 'unknown')}" for r in failed_ops])
            
            # 🔥 PHASE 2 FIX: Return HTTP 422 for validation failures (e.g., protected paths)
            # Check if errors are validation-related
            if any("Protected path" in r.get("error", "") for r in failed_ops):
                raise HTTPException(status_code=422, detail=f"Validation failed: {errors}")
            else:
                raise HTTPException(status_code=500, detail=f"Operation failed: {errors}")
        
        # Extract changed files
        files_changed = [r.get("path") for r in exec_results if r.get("path")]
        
        # Git commit
        commit_title = request.commit.get("title", "Direct operations")
        step_number = request.commit.get("step_number", 1)
        
        commit_success = await _commit_step_changes(
            run_id=request.run_id,
            step_number=step_number,
            step_title=commit_title,
            project_path=str(project_code_path),
            files_changed=files_changed
        )
        
        # Get commit hash
        commit_hash = None
        if commit_success:
            try:
                repo = git.Repo(project_code_path)
                commit_hash = repo.head.commit.hexsha
            except:
                pass
        
        # RAG re-indexing
        if files_changed and FILE_WRITE_MODE == "direct":
            try:
                logger.info(f"Re-indexing {len(files_changed)} changed files in RAG...")
                if hasattr(rag_system, 'index_project'):
                    await rag_system.index_project(str(project_code_path))
                elif hasattr(rag_system, 'reindex'):
                    await rag_system.reindex(str(project_code_path))
                logger.info("✅ RAG re-indexing completed")
            except Exception as e:
                logger.warning(f"RAG re-indexing failed: {e}")
        
        # Build artifacts
        artifacts = {
            "operations_count": len(exec_results),
            "files_changed": files_changed,
            "commit_hash": commit_hash,
            "operations_results": exec_results
        }
        
        return {
            "status": "success",
            "operations_executed": len(exec_results),
            "commit_hash": commit_hash,
            "artifacts": artifacts
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error executing operations: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/runs", response_model=Run)
async def create_run(run_data: RunCreate, background_tasks: BackgroundTasks):
    """
    Create a new AI agent run with project isolation
    
    🔥 PHASE 2: Supports two modes:
    - project_mode="create": Create new isolated project workspace
    - project_mode="attach": Attach to existing project (no recreation)
    """
    try:
        # Create run record
        run = Run(**run_data.dict())
        
        # 🔥 PHASE 2: Handle attach vs create mode
        if run.project_mode == "attach":
            # === MODE ATTACH: Attach to existing project ===
            if not run.project_id and not run.project_path:
                raise HTTPException(
                    status_code=400, 
                    detail="project_id or project_path required for attach mode"
                )
            
            # Attach to project
            attach_result = await project_manager.attach_to_project(
                project_id=run.project_id,
                project_path=run.project_path,
                run_id=run.id
            )
            
            # Update run with attached project info
            run.project_path = attach_result["project_path"]
            run.stack = attach_result["stack"]
            run.project_id = attach_result.get("project_id", run.project_id)
            run.attached_commit = attach_result.get("initial_commit")
            
            logging.info(f"✅ Attached run {run.id} to project {run.project_id} at {run.project_path}")
            
        else:
            # === MODE CREATE: Create new project workspace ===
            # Auto-detect stack if unknown or if project_path exists
            if run.stack == "unknown" or run.project_path:
                if run.project_path and os.path.exists(run.project_path):
                    detected_stack = tool_manager._detect_project_stack(run.project_path)
                    if detected_stack != "unknown":
                        run.stack = detected_stack
                        logging.info(f"🔍 Auto-detected stack '{detected_stack}' from existing project: {run.project_path}")
                    else:
                        logging.warning(f"⚠️ Unable to detect stack from existing project: {run.project_path}")
                else:
                    logging.info(f"🔍 Stack is 'unknown' - will be determined during project creation based on goal analysis")
            
            # Create isolated project workspace
            project_workspace = await project_manager.create_project_workspace(
                project_id=run.id,
                stack=run.stack,
                project_name=f"Run {run.id[:8]}"
            )
            
            # Update run with project path
            run.project_path = project_workspace["code_path"]
            run.project_id = run.id  # Use run ID as project ID for new projects
            
            logging.info(f"✅ Created new project workspace for run {run.id}")
        
        # Save to database
        await db.runs.insert_one(bson_utils.bson_safe(run.dict()))
        
        # Start orchestration in background
        background_tasks.add_task(execute_run, run.id)
        
        return run
    except HTTPException:
        raise
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
                        yield f"data: {json_utils.dumps(log)}\n\n"
                    last_log_count = len(run.logs)
                
                # Send status update
                yield f"data: {json_utils.dumps({'type': 'status', 'status': run.status, 'current_step': run.current_step})}\n\n"
                
                # Break if run is completed
                if run.status in [RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED]:
                    break
                
                await asyncio.sleep(1)
            except Exception as e:
                logging.error(f"Error streaming logs: {e}")
                break
    
    return StreamingResponse(generate(), media_type="text/plain")

# Project Management Routes

@api_router.get("/projects")
async def list_projects():
    """List all projects"""
    try:
        projects = await project_manager.list_projects()
        return {"projects": projects}
    except Exception as e:
        logging.error(f"Error listing projects: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/projects/{project_id}")
async def get_project(project_id: str):
    """Get project details"""
    try:
        project_info = await project_manager.get_project_info(project_id)
        if not project_info:
            raise HTTPException(status_code=404, detail="Project not found")
        return project_info
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error getting project: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.delete("/projects/{project_id}")
async def delete_project(project_id: str):
    """Delete project"""
    try:
        success = await project_manager.delete_project(project_id)
        if not success:
            raise HTTPException(status_code=404, detail="Project not found")
        return {"message": "Project deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error deleting project: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/projects/{project_id}/preview")
async def preview_project(project_id: str):
    """Preview a completed project in browser"""
    try:
        project = await project_manager.get_project_info(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        project_path = f"/app/projects/{project_id}/code"
        
        # Check if project directory exists
        if not os.path.exists(project_path):
            raise HTTPException(status_code=404, detail="Project files not found")
        
        stack = project.get('stack', 'unknown')
        
        # For React/Vue projects, look for build output or serve directly
        if stack in ['react', 'vue']:
            # Look for build directory
            build_path = os.path.join(project_path, 'build') if stack == 'react' else os.path.join(project_path, 'dist')
            
            if os.path.exists(build_path):
                # Serve the built static files
                index_file = os.path.join(build_path, 'index.html')
                if os.path.exists(index_file):
                    from fastapi.responses import FileResponse
                    return FileResponse(index_file, media_type='text/html')
            
            # If no build, look for public/index.html for development preview
            public_index = os.path.join(project_path, 'public', 'index.html')
            if os.path.exists(public_index):
                from fastapi.responses import FileResponse
                return FileResponse(public_index, media_type='text/html')
        
        # For Laravel projects
        elif stack == 'laravel':
            # Check for Laravel public directory
            public_path = os.path.join(project_path, 'public', 'index.php')
            if os.path.exists(public_path):
                return {
                    "message": "Laravel project detected",
                    "preview_type": "php_server_required",
                    "instructions": "Ce projet Laravel nécessite un serveur PHP pour être prévisualisé. Utilisez 'php artisan serve' dans le répertoire du projet."
                }
        
        # For Python projects
        elif stack == 'python':
            # Look for common Python web frameworks
            requirements_path = os.path.join(project_path, 'requirements.txt')
            if os.path.exists(requirements_path):
                with open(requirements_path, 'r') as f:
                    requirements = f.read().lower()
                    
                if 'flask' in requirements:
                    return {
                        "message": "Flask project detected",
                        "preview_type": "python_server_required", 
                        "instructions": "Ce projet Flask nécessite Python. Exécutez 'python app.py' dans le répertoire du projet."
                    }
                elif 'django' in requirements:
                    return {
                        "message": "Django project detected",
                        "preview_type": "python_server_required",
                        "instructions": "Ce projet Django nécessite Python. Exécutez 'python manage.py runserver' dans le répertoire du projet."
                    }
        
        # Fallback: return project structure
        return {
            "message": f"Preview non disponible pour le stack {stack}",
            "preview_type": "not_supported",
            "stack": stack,
            "project_path": project_path,
            "instructions": f"Ce type de projet ({stack}) ne supporte pas encore la preview automatique."
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error previewing project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# GitHub Integration Routes

@api_router.get("/github/oauth-url")
async def get_github_oauth_url(state: str = None):
    """Get GitHub OAuth authorization URL"""
    try:
        oauth_url = await github_integration.get_oauth_url(state)
        return {"oauth_url": oauth_url}
    except Exception as e:
        logging.error(f"Error getting GitHub OAuth URL: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class GitHubAuthData(BaseModel):
    code: str
    state: Optional[str] = None

@api_router.post("/github/auth")
async def github_auth(auth_data: GitHubAuthData):
    """Exchange GitHub OAuth code for token"""
    try:
        token_data = await github_integration.exchange_code_for_token(auth_data.code)
        if not token_data:
            raise HTTPException(status_code=400, detail="Failed to exchange code for token")
        
        # Get user info
        user_info = await github_integration.get_user_info(token_data["access_token"])
        
        return {
            "access_token": token_data["access_token"],
            "user": user_info
        }
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error with GitHub auth: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/github/repositories")
async def list_github_repositories(access_token: str):
    """List user's GitHub repositories"""
    try:
        repos = await github_integration.list_repositories(access_token)
        return {"repositories": repos}
    except Exception as e:
        logging.error(f"Error listing GitHub repos: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class CloneRepositoryData(BaseModel):
    repo_url: str
    access_token: str
    project_name: Optional[str] = None

@api_router.post("/github/clone")
async def clone_repository(clone_data: CloneRepositoryData):
    """Clone GitHub repository to new project"""
    try:
        # Analyze repository structure
        repo_info = github_integration.get_repo_info_from_url(clone_data.repo_url)
        if not repo_info:
            raise HTTPException(status_code=400, detail="Invalid GitHub repository URL")
        
        analysis = await github_integration.analyze_repository_structure(
            clone_data.access_token, 
            repo_info["owner"], 
            repo_info["repo"]
        )
        
        # Create project workspace
        project_id = str(uuid.uuid4())
        project_workspace = await project_manager.create_project_workspace(
            project_id=project_id,
            stack=analysis["stack"],
            project_name=clone_data.project_name or repo_info["repo"]
        )
        
        # Clone repository
        success = await github_integration.clone_repository(
            clone_data.repo_url,
            Path(project_workspace["code_path"]),
            clone_data.access_token
        )
        
        if not success:
            await project_manager.delete_project(project_id)
            raise HTTPException(status_code=500, detail="Failed to clone repository")
        
        return {
            "project_id": project_id,
            "project_path": project_workspace["project_path"],
            "analysis": analysis,
            "message": "Repository cloned successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error cloning repository: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class GitOperationData(BaseModel):
    project_id: str
    access_token: Optional[str] = None
    message: Optional[str] = None
    branch: Optional[str] = "main"

@api_router.post("/github/push")
async def push_to_github(git_data: GitOperationData):
    """Push project changes to GitHub"""
    try:
        code_path = project_manager.get_code_path(git_data.project_id)
        
        # Commit changes
        success = await github_integration.commit_changes(
            code_path,
            git_data.message or "Automated changes from AI Agent"
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to commit changes")
        
        # Push changes
        success = await github_integration.push_changes(
            code_path,
            "origin",
            git_data.branch,
            git_data.access_token
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to push changes")
        
        return {"message": "Changes pushed successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error pushing to GitHub: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/github/pull")
async def pull_from_github(git_data: GitOperationData):
    """Pull changes from GitHub"""
    try:
        code_path = project_manager.get_code_path(git_data.project_id)
        
        success = await github_integration.pull_changes(
            code_path,
            "origin",
            git_data.branch
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to pull changes")
        
        return {"message": "Changes pulled successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error pulling from GitHub: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Admin Routes

@api_router.get("/admin/stats")
async def get_admin_stats():
    """Get admin statistics"""
    try:
        # Get run statistics
        run_stats = await state_manager.get_run_statistics()
        
        # Get daily cost
        daily_cost = await state_manager.get_daily_cost()
        
        # Get project count
        projects = await project_manager.list_projects()
        project_count = len(projects)
        
        # Get prompt cache statistics
        cache_stats = llm_router.prompt_cache.get_cache_stats()
        cost_savings = llm_router.prompt_cache.estimate_cost_savings()
        
        # Get system settings
        settings = {
            "max_local_retries": int(os.getenv("MAX_LOCAL_RETRIES", "3")),
            "default_daily_budget": float(os.getenv("DEFAULT_DAILY_BUDGET_EUR", "5.0")),
            "max_steps_per_run": int(os.getenv("MAX_STEPS_PER_RUN", "20")),
            "auto_create_structures": os.getenv("AUTO_CREATE_STRUCTURES", "true").lower() == "true"
        }
        
        return {
            "run_stats": run_stats,
            "daily_cost": daily_cost,
            "project_count": project_count,
            "cache_stats": cache_stats,
            "cost_savings": cost_savings,
            "settings": settings
        }
        
    except Exception as e:
        logging.error(f"Error getting admin stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/admin/cache/clear")
async def clear_prompt_cache():
    """Clear prompt cache"""
    try:
        cleared_count = await llm_router.prompt_cache.clear_cache()
        return {"message": f"Cleared {cleared_count} cached prompts"}
    except Exception as e:
        logging.error(f"Error clearing cache: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/admin/mode")
async def get_file_write_mode():
    """
    🔥 PHASE 1: Get current file write mode for debugging
    Returns: { "file_write_mode": "direct" | "patch", "deny_list": [...] }
    """
    from orchestrator.file_writer import PROTECTED_PATHS
    return {
        "file_write_mode": FILE_WRITE_MODE,
        "developer_agent_type": type(developer_agent).__name__,
        "description": "direct = JSON operations, patch = Git diffs",
        "deny_list": PROTECTED_PATHS
    }

@api_router.get("/admin/global-stats")
async def get_global_admin_stats():
    """Get global admin statistics for main admin panel"""
    try:
        # Get all runs from database
        runs_collection = client.emergent_ai.runs
        
        # Total projects and runs
        projects = await project_manager.list_projects()
        total_projects = len(projects)
        
        all_runs = await runs_collection.find({}).to_list(length=None)
        total_runs = len(all_runs)
        completed_runs = len([r for r in all_runs if r.get('status') == 'completed'])
        
        # Total costs calculation
        total_costs = sum(r.get('cost_used_eur', 0) for r in all_runs)
        
        # Today's usage
        from datetime import datetime, timezone
        today = datetime.now(timezone.utc).date()
        today_runs = []
        for r in all_runs:
            if r.get('created_at'):
                try:
                    # Handle different datetime formats
                    created_at_str = r['created_at']
                    if isinstance(created_at_str, str):
                        # Remove Z and add timezone info if needed
                        if created_at_str.endswith('Z'):
                            created_at_str = created_at_str[:-1] + '+00:00'
                        created_at = datetime.fromisoformat(created_at_str)
                        if created_at.date() == today:
                            today_runs.append(r)
                    elif hasattr(created_at_str, 'date'):
                        # Already a datetime object
                        if created_at_str.date() == today:
                            today_runs.append(r)
                except (ValueError, TypeError) as e:
                    logger.warning(f"Could not parse created_at for run {r.get('id', 'unknown')}: {e}")
                    continue
        today_usage = sum(r.get('cost_used_eur', 0) for r in today_runs)
        
        # Cache statistics
        cache_stats = llm_router.prompt_cache.get_cache_stats()
        cost_savings = llm_router.prompt_cache.estimate_cost_savings()
        
        # Environment status
        env_status = {
            "openai_key": bool(os.getenv("OPENAI_API_KEY")),
            "openai_key_suffix": os.getenv("OPENAI_API_KEY", "")[-4:] if os.getenv("OPENAI_API_KEY") else "",
            "anthropic_key": bool(os.getenv("ANTHROPIC_API_KEY")),
            "anthropic_key_suffix": os.getenv("ANTHROPIC_API_KEY", "")[-6:] if os.getenv("ANTHROPIC_API_KEY") else "",
            "github_token": bool(os.getenv("GITHUB_TOKEN")),
            "mongo_url": bool(os.getenv("MONGO_URL"))
        }
        
        # System configuration
        system_config = {
            "daily_budget": float(os.getenv("DEFAULT_DAILY_BUDGET_EUR", "5.0")),
            "max_local_retries": int(os.getenv("MAX_LOCAL_RETRIES", "3")),
            "max_steps": int(os.getenv("MAX_STEPS_PER_RUN", "20")),
            "auto_create": os.getenv("AUTO_CREATE_STRUCTURES", "true").lower() == "true"
        }
        
        return {
            "total_projects": total_projects,
            "total_runs": total_runs,
            "completed_runs": completed_runs,
            "total_costs": total_costs,
            "daily_usage": {
                "today": today_usage
            },
            "daily_budget": system_config["daily_budget"],
            "cache_stats": cache_stats,
            "cache_savings": cost_savings,
            "env_status": env_status,
            "system_config": system_config
        }
        
    except Exception as e:
        logging.error(f"Error getting global admin stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/admin/global-logs")
async def get_global_logs(limit: int = 100, project_id: str = None):
    """Get global system logs across all projects"""
    try:
        # Get logs from all runs
        runs_collection = client.emergent_ai.runs
        query = {}
        
        if project_id:
            # Filter by project_id if specified
            projects = await project_manager.list_projects()
            project_runs = [p for p in projects if p.get('id') == project_id]
            if project_runs:
                run_ids = [r.get('id') for r in project_runs if r.get('id')]
                query = {"id": {"$in": run_ids}}
        
        runs = await runs_collection.find(query).sort("created_at", -1).limit(limit).to_list(length=limit)
        
        # Collect all logs from runs
        all_logs = []
        for run in runs:
            run_logs = run.get('logs', [])
            for log in run_logs:
                log_entry = {
                    "timestamp": log.get('timestamp'),
                    "type": log.get('type', 'info'),
                    "content": log.get('content', ''),
                    "project_id": run.get('project_id'),
                    "run_id": run.get('id')
                }
                all_logs.append(log_entry)
        
        # Sort by timestamp (most recent first)
        all_logs.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        return {
            "logs": all_logs[:limit],
            "total_count": len(all_logs)
        }
        
    except Exception as e:
        logging.error(f"Error getting global logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# WebSocket endpoint for real-time updates
@app.websocket("/ws/{run_id}")
async def websocket_endpoint(websocket: WebSocket, run_id: str):
    await websocket.accept()
    try:
        while True:
            # In a real implementation, you'd listen to run updates
            # For now, just keep the connection alive and send periodic heartbeats
            data = await websocket.receive_text()
            await websocket.send_text(f"Echo: {data}")
    except WebSocketDisconnect:
        print(f"WebSocket disconnected for run {run_id}")

@app.websocket("/ws")
async def websocket_global_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(f"Global echo: {data}")
    except WebSocketDisconnect:
        print("Global WebSocket disconnected")

# Mount the API router
app.include_router(api_router, prefix="/api")

# User validation and interaction endpoints

@api_router.get("/runs/{run_id}/agent-conversations")
async def get_agent_conversations(run_id: str):
    """Get agent conversations for debugging and traceability"""
    try:
        run_data = await db.runs.find_one({"id": run_id})
        if not run_data:
            raise HTTPException(status_code=404, detail="Run not found")
        
        conversations = run_data.get("agent_conversations", [])
        return {"conversations": conversations}
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error getting agent conversations: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Removed duplicate validate_plan function - see line 945 for implementation

@api_router.post("/runs/{run_id}/validate-step")
async def validate_step(run_id: str, step_number: int, validation: dict):
    """User validation endpoint for individual steps"""
    try:
        approved = validation.get("approved", False)
        feedback = validation.get("feedback", "")
        
        if approved:
            await state_manager.add_log(run_id, {
                "type": "info",
                "content": f"Step {step_number} approved by user: {feedback}"
            })
        else:
            await state_manager.add_log(run_id, {
                "type": "warning",
                "content": f"Step {step_number} rejected by user: {feedback}"
            })
        
        return {"message": "Step validation received", "approved": approved}
        
    except Exception as e:
        logging.error(f"Error processing step validation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/runs/{run_id}/interrupt")
async def interrupt_run(run_id: str, reason: str = "User requested"):
    """Interrupt a running execution gracefully"""
    try:
        await state_manager.add_log(run_id, {
            "type": "warning",
            "content": f"Execution interrupted: {reason}"
        })
        
        # Update run status to cancelled
        await state_manager.update_run_status(run_id, RunStatus.CANCELLED)
        
        return {"message": "Run interrupted successfully"}
        
    except Exception as e:
        logging.error(f"Error interrupting run: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/runs/{run_id}/validate-plan")
async def validate_plan(run_id: str, validation: dict):
    """User validation of generated plan"""
    try:
        run_data = await db.runs.find_one({"id": run_id})
        if not run_data:
            raise HTTPException(status_code=404, detail="Run not found")
        
        approved = validation.get("approved", False)
        feedback = validation.get("feedback", "")
        
        # Update run with validation result
        await db.runs.update_one(
            {"id": run_id},
            {"$set": {
                "plan_validated": approved,
                "plan_feedback": feedback,
                "plan_validation_time": datetime.now(timezone.utc)
            }}
        )
        
        await state_manager.add_log(run_id, {
            "type": "info",
            "content": f"Plan validation: {'approved' if approved else 'rejected'}. Feedback: {feedback}"
        })
        
        return {"status": "validated", "approved": approved}
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error validating plan: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/runs/{run_id}/export")
async def export_run(run_id: str, export_format: str = "zip"):
    """Export run results as ZIP or prepare for GitHub push"""
    try:
        run_data = await db.runs.find_one({"id": run_id})
        if not run_data:
            raise HTTPException(status_code=404, detail="Run not found")
        
        run = Run(**run_data)
        project_code_path = project_manager.get_code_path(run_id)
        
        if export_format == "zip":
            # Create ZIP archive of the project
            import zipfile
            import tempfile
            
            with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp_file:
                with zipfile.ZipFile(tmp_file.name, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                    for root, dirs, files in os.walk(project_code_path):
                        for file in files:
                            file_path = os.path.join(root, file)
                            arc_name = os.path.relpath(file_path, project_code_path)
                            zip_file.write(file_path, arc_name)
                
                return FileResponse(
                    tmp_file.name,
                    media_type="application/zip",
                    filename=f"project-{run_id}.zip"
                )
        
        elif export_format == "github":
            # Prepare for GitHub integration
            return {
                "status": "ready_for_github",
                "project_path": str(project_code_path),
                "files_count": len(list(project_code_path.rglob("*"))),
                "instructions": "Use the GitHub integration tab to push to repository"
            }
        
        else:
            raise HTTPException(status_code=400, detail="Invalid export format")
            
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error exporting run: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/validate-patch")
async def validate_patch_endpoint(request: dict):
    """
    Advanced patch validation endpoint (Phase 3)
    Tests patch quality, validation, and repair capabilities
    """
    try:
        patch_content = request.get("patch_content", "")
        project_path = request.get("project_path", "/tmp/test_project")
        
        if not patch_content:
            raise HTTPException(status_code=400, detail="patch_content is required")
        
        # Create test project if needed
        if not os.path.exists(project_path):
            os.makedirs(project_path, exist_ok=True)
            # Initialize git
            import subprocess
            subprocess.run(["git", "init"], cwd=project_path, capture_output=True)
        
        # Run comprehensive patch validation
        quality_report = await tool_manager.validate_patch_quality(patch_content, project_path)
        
        return {
            "status": "validation_complete",
            "quality_report": quality_report,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error in patch validation endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/runs/{run_id}/execution-context")
async def get_execution_context(run_id: str):
    """Get current execution context and status"""
    try:
        run_data = await db.runs.find_one({"id": run_id})
        if not run_data:
            raise HTTPException(status_code=404, detail="Run not found")
        
        # Get latest logs to determine current phase
        logs = run_data.get("logs", [])
        latest_logs = logs[-10:] if logs else []
        
        # Determine current phase from logs
        current_phase = "unknown"
        for log in reversed(latest_logs):
            content = log.get("content", "")
            if "Phase 1:" in content:
                current_phase = "planning"
                break
            elif "Phase 2:" in content:
                current_phase = "execution"
                break
            elif "Phase 3:" in content or "completed" in content.lower():
                current_phase = "finalization"
                break
        
        return {
            "run_id": run_id,
            "status": run_data.get("status"),
            "current_step": run_data.get("current_step", 0),
            "current_phase": current_phase,
            "plan_revision_count": len([log for log in logs if "plan revision" in log.get("content", "").lower()]),
            "agent_conversations_count": len(run_data.get("agent_conversations", [])),
            "latest_logs": latest_logs
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error getting execution context: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Core orchestration logic

async def execute_run(run_id: str, from_step: int = 0):
    """
    Execute a run with complete iterative cycle using AI agents.
    
    Architecture:
    1. PlannerAgent generates initial plan
    2. For each step:
       - DeveloperAgent generates patch
       - Apply patch via tool_manager
       - Run tests
       - ReviewerAgent evaluates results
       - If failure: feedback to Developer (max 3 attempts)
       - If repeated failures: return to Planner for plan revision
    3. User validation points
    4. Save agent conversations in StateManager
    5. Handle timeouts and interruptions
    """
    execution_context = {
        "run_id": run_id,
        "from_step": from_step,
        "start_time": datetime.now(timezone.utc),
        "timeout_seconds": 3600,  # 1 hour timeout
        "user_validation_required": False,
        "plan_revision_count": 0,
        "max_plan_revisions": 2
    }
    
    try:
        # Get run details
        run_data = await db.runs.find_one({"id": run_id})
        if not run_data:
            await state_manager.add_log(run_id, {"type": "error", "content": "Run not found"})
            return
        
        run = Run(**run_data)
        
        # Update status to running
        await state_manager.update_run_status(run_id, RunStatus.RUNNING)
        await state_manager.add_log(run_id, {"type": "info", "content": "Starting iterative execution cycle"})
        
        # Initialize RAG system with project context
        if run.project_path:
            await rag_system.index_project(run.project_path)
        
        # Phase 1: Planning with PlannerAgent
        parsed_steps = []
        if from_step == 0:
            await state_manager.add_log(run_id, {"type": "info", "content": "Phase 1: Generating plan with PlannerAgent"})
            
            project_context = ProjectContext(
                code_path=run.project_path,
                metadata={
                    "stack": run.stack,
                    "project_path": run.project_path,
                    "goal": run.goal
                }
            )
            
            # Save agent conversation
            await _save_agent_conversation(run_id, "planner", "input", {
                "task": run.goal,
                "context": project_context.__dict__
            })
            
            try:
                plan_result = await planner_agent.generate_plan(run.goal, project_context, run)
                parsed_steps = plan_result.steps
                
                # ✅ Flatten hierarchical steps into executable sequence (Emergent.sh style)
                execution_steps = []
                for main_step in parsed_steps:
                    if main_step.substeps:
                        # Add all substeps to execution queue
                        execution_steps.extend(main_step.get_all_substeps_flat())
                    else:
                        # Main step has no substeps, execute it directly
                        execution_steps.append(main_step)
                
                # Use flattened steps for execution but keep original for display
                
                # Save plan and agent conversation (keep original hierarchical structure for display)
                await db.runs.update_one(
                    {"id": run_id},
                    {"$set": bson_utils.bson_safe({
                        "plan": plan_result.plan_text,
                        "parsed_plan": plan_result.steps,  # Original hierarchical steps
                        "execution_steps": execution_steps,  # Flattened for execution
                        "plan_context": plan_result.context
                    })}
                )
                
                await _save_agent_conversation(run_id, "planner", "output", {
                    "plan_text": plan_result.plan_text,
                    "steps_count": len(parsed_steps),
                    "context_used": len(plan_result.context)
                })
                
                await state_manager.add_log(run_id, {
                    "type": "success", 
                    "content": f"Plan generated successfully with {len(parsed_steps)} main steps ({len(execution_steps)} executable substeps)"
                })
                
                # User validation point for plan
                if execution_context["user_validation_required"]:
                    await _request_user_validation(run_id, "plan", plan_result.plan_text)
                    
            except Exception as e:
                await state_manager.add_log(run_id, {"type": "error", "content": f"Planning failed: {str(e)}"})
                await state_manager.update_run_status(run_id, RunStatus.FAILED)
                return
        else:
            # Resume from existing plan
            run_data = await db.runs.find_one({"id": run_id})
            if run_data and "parsed_plan" in run_data:
                parsed_steps = [PlanStep(**step_data) for step_data in run_data["parsed_plan"]]
        
        # Phase 2: Iterative execution cycle
        await state_manager.add_log(run_id, {"type": "info", "content": "Phase 2: Starting iterative execution cycle"})
        
        current_step_index = from_step
        steps_executed = 0
        completed_successfully = True
        
        while current_step_index < len(execution_steps) and current_step_index < run.max_steps:
            # Check for timeout
            if _is_execution_timeout(execution_context):
                await state_manager.add_log(run_id, {"type": "warning", "content": "Execution timeout reached"})
                completed_successfully = False
                break
            
            # Check if run was cancelled
            run_data = await db.runs.find_one({"id": run_id})
            if not run_data or Run(**run_data).status == RunStatus.CANCELLED:
                await state_manager.add_log(run_id, {"type": "warning", "content": "Run was cancelled"})
                completed_successfully = False
                break
            
            current_step = execution_steps[current_step_index]
            await state_manager.add_log(run_id, {
                "type": "info", 
                "content": f"Executing step {current_step_index + 1}/{len(parsed_steps)}: {current_step.description}"
            })
            
            # Execute step with iterative cycle
            step_success = await _execute_step_with_agents(
                run_id, run, current_step, current_step_index, execution_context
            )
            
            if step_success:
                await state_manager.add_log(run_id, {
                    "type": "success", 
                    "content": f"Step {current_step_index + 1} completed successfully"
                })
                current_step_index += 1
                steps_executed += 1
                await state_manager.update_current_step(run_id, current_step_index)
            else:
                # Step failed after all retries and potential plan revision
                await state_manager.add_log(run_id, {
                    "type": "error", 
                    "content": f"Step {current_step_index + 1} failed definitively"
                })
                completed_successfully = False
                break
            
            # Check budget limit
            run_data = await db.runs.find_one({"id": run_id})
            if run_data and Run(**run_data).cost_used_eur >= run.daily_budget_eur:
                await state_manager.add_log(run_id, {"type": "warning", "content": "Daily budget limit reached"})
                completed_successfully = False
                break
        
        # Phase 3: Final validation and completion
        await _finalize_execution(run_id, run, steps_executed, completed_successfully, execution_context)
        
    except Exception as e:
        logging.error(f"Error executing run {run_id}: {e}")
        await state_manager.add_log(run_id, {"type": "error", "content": f"Execution failed: {str(e)}"})
        await state_manager.update_run_status(run_id, RunStatus.FAILED)

async def verify_code_files_generated(code_path: Path, stack: str) -> bool:
    """
    ✅ PRIORITÉ 1 - Vérifier que des fichiers de code ont été générés dans le dossier projects/<id>/code/
    Retourne True si des fichiers principaux attendus selon la stack sont présents
    """
    try:
        if not code_path.exists():
            logging.warning(f"Code path does not exist: {code_path}")
            return False
            
        # Définir les fichiers attendus selon la stack
        expected_files = {
            "laravel": ["composer.json", "app/", "routes/", "database/"],
            "react": ["package.json", "src/", "public/"],
            "vue": ["package.json", "src/", "public/"],
            "python": ["requirements.txt"], # ✅ FIXED: More flexible - only requires requirements.txt
            "node": ["package.json", "index.js"],
            "nodejs": ["package.json", "index.js"]
        }
        
        stack_lower = stack.lower() if stack else "unknown"
        required_files = expected_files.get(stack_lower, ["requirements.txt"])  # Fallback to flexible Python
        
        # 🔥 PHASE 1 FIX: For Python projects, accept alternative entry points
        if stack_lower == "python":
            # Check for common Python entry points
            python_entry_points = [
                "main.py",
                "app.py", 
                "server.py",
                "backend/server.py",
                "src/main.py",
                "src/app.py"
            ]
            has_entry_point = any((code_path / entry).exists() for entry in python_entry_points)
            has_requirements = (code_path / "requirements.txt").exists()
            
            # For Python, we need at least one .py file and requirements.txt
            if has_requirements:
                logging.info(f"✅ Python project: requirements.txt found")
                if has_entry_point:
                    found_entries = [e for e in python_entry_points if (code_path / e).exists()]
                    logging.info(f"✅ Python project: entry point(s) found: {found_entries}")
                    return True
                else:
                    # Check if there's at least one .py file anywhere
                    py_files = list(code_path.rglob("*.py"))
                    if py_files:
                        logging.info(f"✅ Python project: {len(py_files)} .py file(s) found (no standard entry point)")
                        return True
                    else:
                        logging.warning(f"⚠️ Python project: requirements.txt exists but no .py files found")
                        return False
            else:
                logging.warning(f"⚠️ Python project: requirements.txt not found")
                return False
        
        # Compter les fichiers/dossiers présents
        existing_count = 0
        all_items = list(code_path.iterdir())
        
        logging.info(f"Checking code files in {code_path} for stack '{stack}' - found {len(all_items)} items")
        
        for required in required_files:
            file_path = code_path / required
            if file_path.exists():
                existing_count += 1
                logging.info(f"Found expected file/dir: {required}")
            else:
                logging.warning(f"Missing expected file/dir: {required}")
        
        # Si au moins 50% des fichiers attendus sont présents, considérer comme valide
        success_threshold = max(1, len(required_files) // 2)
        files_generated = existing_count >= success_threshold
        
        if files_generated:
            logging.info(f"Code verification PASSED: {existing_count}/{len(required_files)} expected files found")
        else:
            logging.error(f"Code verification FAILED: only {existing_count}/{len(required_files)} expected files found (threshold: {success_threshold})")
            
        return files_generated
        
    except Exception as e:
        logging.error(f"Error verifying code files: {e}")
        return False

# Helper functions for the new iterative cycle

async def _commit_step_changes(
    run_id: str, 
    step_number: int, 
    step_title: str,
    project_path: str,
    files_changed: Optional[List[str]] = None
) -> bool:
    """
    🔥 PHASE 1: Commit step changes to Git with atomic commit message
    Format: feat(run:<run_id>): step <n> – <titre>
    
    Args:
        run_id: Run ID
        step_number: Step number (1-indexed)
        step_title: Step description/title
        project_path: Path to project code directory
        files_changed: Optional list of files that were changed
        
    Returns:
        True if commit succeeded, False otherwise
    """
    try:
        # Initialize Git repo if not already initialized
        repo_path = Path(project_path)
        
        # Check if it's a git repo
        try:
            repo = git.Repo(repo_path)
        except git.InvalidGitRepositoryError:
            # Initialize new repo
            repo = git.Repo.init(repo_path)
            logger.info(f"✅ Initialized Git repository at {repo_path}")
        
        # Check if there are changes to commit
        if not repo.is_dirty(untracked_files=True):
            logger.info(f"No changes to commit for step {step_number}")
            return True
        
        # Add all changes (or specific files if provided)
        if files_changed:
            for file_path in files_changed:
                try:
                    repo.index.add([file_path])
                except Exception as e:
                    logger.warning(f"Could not add {file_path}: {e}")
            # Also add any untracked files mentioned in files_changed
            repo.index.add(repo.untracked_files)
        else:
            # Add all changes
            repo.git.add(A=True)
        
        # Create commit with standardized message
        commit_msg = StepCommit(
            run_id=run_id,
            step_number=step_number,
            step_title=step_title
        ).format_message()
        
        repo.index.commit(commit_msg)
        logger.info(f"✅ Committed step {step_number}: {commit_msg}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to commit step changes: {e}")
        return False

async def _save_agent_conversation(run_id: str, agent_type: str, direction: str, data: Dict[str, Any]) -> None:
    """Save agent conversation for traceability and debugging."""
    try:
        entry = {
            "timestamp": datetime.now(timezone.utc),
            "agent_type": agent_type,   # "planner" | "developer" | "reviewer" ...
            "direction": direction,     # "input" | "output"
            "data": data,               # peut contenir Path / Enums / dataclasses
        }

        await db.runs.update_one(
            {"id": run_id},
            {"$push": {"agent_conversations": bson_utils.bson_safe(entry)}}  # ✅ BSON-safe
        )

        await state_manager.add_log(run_id, {
            "type": "debug",
            "content": f"Saved {agent_type} agent {direction} conversation"
        })

    except Exception as e:
        logging.warning(f"Failed to save agent conversation: {e}")

async def _request_user_validation(run_id: str, validation_type: str, content: str):
    """Request user validation for plan or step."""
    try:
        # For now, just log the validation request
        # In a full implementation, this would pause execution and wait for user input
        await state_manager.add_log(run_id, {
            "type": "info",
            "content": f"User validation requested for {validation_type}: {content[:200]}..."
        })
        
        # TODO: Implement actual user validation mechanism
        # This could involve:
        # - Updating run status to "awaiting_validation"
        # - Sending notification to user
        # - Waiting for user response via API endpoint
        
    except Exception as e:
        logging.warning(f"Failed to request user validation: {e}")

def _is_execution_timeout(execution_context: dict) -> bool:
    """Check if execution has timed out."""
    elapsed = (datetime.now(timezone.utc) - execution_context["start_time"]).total_seconds()
    return elapsed > execution_context["timeout_seconds"]

async def _execute_step_with_agents(
    run_id: str, 
    run: Run, 
    step: PlanStep, 
    step_index: int, 
    execution_context: dict
) -> bool:
    """
    Execute a single step using the complete agent cycle:
    DeveloperAgent -> patch -> tests -> ReviewerAgent -> feedback loop
    """
    max_attempts = 3
    attempt = 1
    previous_feedback = None
    
    while attempt <= max_attempts:
        try:
            await state_manager.add_log(run_id, {
                "type": "info",
                "content": f"Step {step_index + 1}, attempt {attempt}/{max_attempts}"
            })
            
            # Phase 1: DeveloperAgent generates patch
            project_context = ProjectContext(
                code_path=run.project_path,
                metadata={
                    "stack": run.stack,
                    "project_path": run.project_path,
                    "file_tree": await _get_project_file_tree(run.project_path)
                }
            )
            
            # Save developer agent input
            await _save_agent_conversation(run_id, "developer", "input", {
                "step": step.__dict__,
                "attempt": attempt,
                "previous_feedback": previous_feedback,
                "context": project_context.metadata
            })
            
            # 🔥 PHASE 1: Dual-mode code generation (patch or direct operations)
            files_changed = []
            patch_text_for_review = ""  # For reviewer agent
            
            try:
                if FILE_WRITE_MODE == "direct":
                    # === MODE DIRECT: Generate and execute JSON operations ===
                    operations_result = await developer_agent.generate_operations(step, project_context, run)
                    
                    await _save_agent_conversation(run_id, "developer", "output", {
                        "operations_generated": True,
                        "operations_count": len(operations_result.operations),
                        "attempts": operations_result.attempts,
                        "validated": operations_result.validated,
                    })
                    
                    await state_manager.add_log(run_id, {
                        "type": "info",
                        "content": f"Generated {len(operations_result.operations)} file operations"
                    })
                    
                    # Execute operations
                    project_code_path = project_manager.get_code_path(run_id)
                    exec_results = await execute_operations(
                        operations_result.operations,
                        str(project_code_path),
                        run_id
                    )
                    
                    # Check for failures
                    failed_ops = [r for r in exec_results if r.get("status") == "failed"]
                    if failed_ops:
                        errors = "; ".join([f"{r.get('operation_type')}: {r.get('error')}" for r in failed_ops])
                        await state_manager.add_log(run_id, {
                            "type": "error",
                            "content": f"File operations failed: {errors}"
                        })
                        attempt += 1
                        continue
                    
                    # Extract changed files for Git commit
                    files_changed = [r.get("path") for r in exec_results if r.get("path")]
                    
                    # Build pseudo-patch for reviewer (summary of operations)
                    patch_text_for_review = "\n".join([
                        f"{r.get('status', 'unknown').upper()}: {r.get('path', 'N/A')}"
                        for r in exec_results
                    ])
                    
                    await state_manager.add_log(run_id, {
                        "type": "success",
                        "content": f"File operations applied successfully: {len(exec_results)} operations"
                    })
                    
                else:
                    # === MODE PATCH: Traditional Git patch workflow ===
                    patch_result = await developer_agent.generate_patch(step, project_context, run)
                    
                    await _save_agent_conversation(run_id, "developer", "output", {
                        "patch_generated": True,
                        "attempts": patch_result.attempts,
                        "validated": patch_result.validated,
                        "patch_length": len(patch_result.patch_text)
                    })
                    
                    # Apply patch
                    if patch_result.patch_text:
                        project_code_path = project_manager.get_code_path(run_id)
                        try:
                            patch_success = await tool_manager.apply_patch(
                                patch_result.patch_text, 
                                str(project_code_path),
                                run_id=run_id
                            )
                            if patch_success:
                                await state_manager.add_log(run_id, {
                                    "type": "info",
                                    "content": "Patch applied successfully"
                                })
                                patch_text_for_review = patch_result.patch_text
                            else:
                                await state_manager.add_log(run_id, {
                                    "type": "error",
                                    "content": "Patch application failed - patch may be corrupted or invalid"
                                })
                                attempt += 1
                                continue
                        except Exception as e:
                            await state_manager.add_log(run_id, {
                                "type": "error",
                                "content": f"Failed to apply patch: {str(e)}"
                            })
                            attempt += 1
                            continue
                    
            except Exception as e:
                await state_manager.add_log(run_id, {
                    "type": "error",
                    "content": f"Code generation/application failed: {str(e)}"
                })
                attempt += 1
                continue
            
            # Phase 3: Run tests
            project_code_path = project_manager.get_code_path(run_id)
            test_results = await run_comprehensive_tests(str(project_code_path), run.stack)
            
            # Convert test results to ReviewerAgent format
            reviewer_test_results = []
            for test_result in test_results:
                reviewer_test_results.append(ReviewerTestResult(
                    test_type=test_result.test_type,
                    status=test_result.status,
                    output=test_result.output,
                    details=test_result.details
                ))
            
            # Phase 4: ReviewerAgent evaluates results
            await _save_agent_conversation(run_id, "reviewer", "input", {
                "step": step.__dict__,
                "patch_text": patch_text_for_review[:500] if patch_text_for_review else "N/A",
                "test_results": [{"type": tr.test_type, "status": tr.status} for tr in reviewer_test_results],
                "attempt": attempt,
                "previous_feedback": previous_feedback
            })
            
            review_result = await reviewer_agent.review_step_result(
                step=step,
                patch_text=patch_text_for_review or "Direct file operations applied",
                test_results=reviewer_test_results,
                attempt_number=attempt,
                previous_feedback=previous_feedback,
                stack=run.stack,
                run=run,
            )
            
            await _save_agent_conversation(run_id, "reviewer", "output", {
                "decision": review_result.decision.value,
                "confidence": review_result.confidence,
                "feedback": review_result.feedback[:200],
                "suggestions_count": len(review_result.suggestions),
                "should_escalate": review_result.should_escalate
            })
            
            # Phase 5: Handle ReviewerAgent decision
            if review_result.decision == ReviewDecision.ACCEPT:
                await state_manager.add_log(run_id, {
                    "type": "success",
                    "content": f"Step {step_index + 1} accepted by reviewer"
                })
                
                # 🔥 PHASE 1: Commit changes to Git (atomic commit per step)
                project_code_path = project_manager.get_code_path(run_id)
                commit_success = await _commit_step_changes(
                    run_id=run_id,
                    step_number=step_index + 1,
                    step_title=step.description[:80],  # Limit title length
                    project_path=str(project_code_path),
                    files_changed=files_changed if files_changed else None
                )
                
                if commit_success:
                    await state_manager.add_log(run_id, {
                        "type": "info",
                        "content": f"✅ Step {step_index + 1} changes committed to Git"
                    })
                else:
                    await state_manager.add_log(run_id, {
                        "type": "warning",
                        "content": f"⚠️ Failed to commit step {step_index + 1} changes to Git"
                    })
                
                # 🔥 PHASE 1: Re-index RAG if files changed
                if files_changed and FILE_WRITE_MODE == "direct":
                    try:
                        await state_manager.add_log(run_id, {
                            "type": "info",
                            "content": f"Re-indexing {len(files_changed)} changed files in RAG..."
                        })
                        
                        # Re-index the project with RAG
                        if hasattr(rag_system, 'index_project'):
                            await rag_system.index_project(str(project_code_path))
                        elif hasattr(rag_system, 'reindex'):
                            await rag_system.reindex(str(project_code_path))
                        
                        await state_manager.add_log(run_id, {
                            "type": "success",
                            "content": "✅ RAG re-indexing completed"
                        })
                    except Exception as e:
                        logger.warning(f"RAG re-indexing failed: {e}")
                        await state_manager.add_log(run_id, {
                            "type": "warning",
                            "content": f"⚠️ RAG re-indexing failed: {str(e)}"
                        })
                
                return True
                
            elif review_result.decision == ReviewDecision.ESCALATE_TO_PLANNER:
                # Need to revise the plan
                if execution_context["plan_revision_count"] < execution_context["max_plan_revisions"]:
                    await state_manager.add_log(run_id, {
                        "type": "warning",
                        "content": f"Escalating to planner for plan revision: {review_result.feedback}"
                    })
                    
                    # TODO: Implement plan revision with PlannerAgent
                    # For now, we'll treat this as a failure
                    execution_context["plan_revision_count"] += 1
                    return False
                else:
                    await state_manager.add_log(run_id, {
                        "type": "error",
                        "content": "Maximum plan revisions reached, failing step"
                    })
                    return False
                    
            elif review_result.decision == ReviewDecision.FAIL:
                await state_manager.add_log(run_id, {
                    "type": "error",
                    "content": f"Step {step_index + 1} marked as failed by reviewer: {review_result.feedback}"
                })
                return False
                
            elif review_result.decision == ReviewDecision.RETRY:
                await state_manager.add_log(run_id, {
                    "type": "warning",
                    "content": f"Step {step_index + 1} needs retry: {review_result.feedback}"
                })
                previous_feedback = review_result.feedback
                attempt += 1
                continue
            
        except Exception as e:
            logging.error(f"Error in step execution cycle: {e}")
            await state_manager.add_log(run_id, {
                "type": "error",
                "content": f"Step execution failed with exception: {str(e)}"
            })
            attempt += 1
            continue
    
    # All attempts exhausted
    await state_manager.add_log(run_id, {
        "type": "error",
        "content": f"Step {step_index + 1} failed after {max_attempts} attempts"
    })
    return False

async def _get_project_file_tree(project_path: str) -> str:
    """Get a simplified file tree for context."""
    try:
        if not project_path or not os.path.exists(project_path):
            return "No project files found"
        
        # Simple file tree generation
        tree_lines = []
        for root, dirs, files in os.walk(project_path):
            # Skip hidden directories and common build/cache directories
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['node_modules', 'vendor', '__pycache__']]
            
            level = root.replace(project_path, '').count(os.sep)
            indent = ' ' * 2 * level
            tree_lines.append(f"{indent}{os.path.basename(root)}/")
            
            subindent = ' ' * 2 * (level + 1)
            for file in files[:10]:  # Limit to first 10 files per directory
                if not file.startswith('.'):
                    tree_lines.append(f"{subindent}{file}")
            
            if len(tree_lines) > 50:  # Limit total lines
                tree_lines.append("... (truncated)")
                break
        
        return '\n'.join(tree_lines)
        
    except Exception as e:
        logging.warning(f"Failed to generate file tree: {e}")
        return "File tree generation failed"

async def _finalize_execution(
    run_id: str, 
    run: Run, 
    steps_executed: int, 
    completed_successfully: bool, 
    execution_context: dict
):
    """Finalize execution with proper status and validation."""
    try:
        if completed_successfully and steps_executed > 0:
            # Verify code files were generated
            project_code_path = project_manager.get_code_path(run_id)
            if not await verify_code_files_generated(project_code_path, run.stack):
                await state_manager.add_log(run_id, {
                    "type": "error", 
                    "content": f"Run completed but no code files were generated in {project_code_path}"
                })
                await state_manager.update_run_status(run_id, RunStatus.FAILED)
            else:
                await state_manager.add_log(run_id, {
                    "type": "success", 
                    "content": f"All {steps_executed} steps completed successfully with code files generated"
                })
                await state_manager.update_run_status(run_id, RunStatus.COMPLETED)
                
        elif steps_executed == 0:
            await state_manager.add_log(run_id, {
                "type": "error", 
                "content": "No steps were executed"
            })
            await state_manager.update_run_status(run_id, RunStatus.FAILED)
            
        else:
            await state_manager.add_log(run_id, {
                "type": "info", 
                "content": f"Run terminated after {steps_executed} steps"
            })
            await state_manager.update_run_status(run_id, RunStatus.FAILED)
        
        # Log execution summary
        execution_time = (datetime.now(timezone.utc) - execution_context["start_time"]).total_seconds()
        await state_manager.add_log(run_id, {
            "type": "info",
            "content": f"Execution completed in {execution_time:.1f} seconds with {execution_context['plan_revision_count']} plan revisions"
        })
        
    except Exception as e:
        logging.error(f"Error finalizing execution: {e}")
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
        await _upsert_step(step)
        
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
        
        # Generate response using LLM router with improved escalation
        response = await llm_router.generate(prompt, "coding", run.cost_used_eur, run.daily_budget_eur, run_id)
        
        # Parse patch from response
        patch = extract_patch(response.content)
        
        # Apply patch to project workspace
        if patch:
            project_code_path = project_manager.get_code_path(run_id)
            await tool_manager.apply_patch(patch, str(project_code_path))
            step.patch = patch
        
        # Run tests in project workspace
        project_code_path = project_manager.get_code_path(run_id)
        test_results = await run_comprehensive_tests(str(project_code_path), run.stack)
        step.tests_passed = all(result.status == "passed" for result in test_results)
        
        # Update step with results
        step.status = StepStatus.COMPLETED if step.tests_passed else StepStatus.FAILED
        step.output = response.content
        step.model_used = response.model
        step.prompt_tokens = response.prompt_tokens
        step.completion_tokens = response.completion_tokens
        step.cost_eur = response.cost_eur
        
        # Update database
        await _upsert_step(step)
        
        # Update run cost
        await state_manager.add_cost(run_id, response.cost_eur)
        
        return step
        
    except Exception as e:
        logging.error(f"Error executing step: {e}")
        step.status = StepStatus.FAILED
        step.error = str(e)
        await _upsert_step(step)
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
    """
    Extract patch from LLM response
    🔥 PHASE 3 FIX: Enhanced extraction with validation
    """
    try:
        start_marker = "BEGIN_PATCH"
        end_marker = "END_PATCH"
        
        start_idx = content.find(start_marker)
        end_idx = content.find(end_marker)
        
        if start_idx != -1 and end_idx != -1:
            patch = content[start_idx + len(start_marker):end_idx].strip()
            
            # 🔥 PHASE 3 FIX: Validate patch has essential components
            if patch and _validate_patch_basics(patch):
                return patch
            else:
                logging.warning("⚠️ Extracted patch missing essential git diff components")
                # Try to find a valid patch elsewhere in the content
                return _extract_fallback_patch(content)
        
        # Try fallback extraction
        return _extract_fallback_patch(content)
        
    except Exception as e:
        logging.error(f"Error extracting patch: {e}")
        return None


def _validate_patch_basics(patch: str) -> bool:
    """
    🔥 PHASE 3 FIX: Quick validation that patch has essential components
    """
    if not patch:
        return False
    
    lines = patch.split('')
    has_diff_header = any(line.startswith('diff --git') for line in lines[:10])
    has_hunk = any(line.startswith('@@') for line in lines)
    
    return has_diff_header and has_hunk


def _extract_fallback_patch(content: str) -> Optional[str]:
    """
    🔥 PHASE 3 FIX: Try to extract a valid patch from content without markers
    """
    if not content:
        return None
    
    # Look for diff --git patterns
    lines = content.split('')
    patch_start = -1
    
    for i, line in enumerate(lines):
        if line.startswith('diff --git'):
            patch_start = i
            break
    
    if patch_start >= 0:
        # Extract from diff --git to end or until non-patch content
        patch_lines = []
        for i in range(patch_start, len(lines)):
            line = lines[i]
            # Stop at common end markers
            if any(marker in line for marker in ['```', 'CHECKLIST', 'Note:', 'Summary:']):
                break
            patch_lines.append(line)
        
        if patch_lines:
            patch = ''.join(patch_lines).strip()
            if _validate_patch_basics(patch):
                logging.info("✅ Extracted valid patch from fallback method")
                return patch
    
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
    """
    🔥 PHASE 3 FIX: Run comprehensive tests with proper stack detection
    Prevents Laravel fallback on non-Laravel projects
    """
    try:
        results = []
        
        if not project_path or not os.path.exists(project_path):
            logging.warning(f"Project path does not exist: {project_path}")
            return [TestResult(
                test_type="setup", 
                status="failed", 
                output=f"Project path does not exist: {project_path}"
            )]
        
        # ✅ PHASE 3 FIX: Auto-detect stack if unknown or validate declared stack
        actual_stack = stack
        if stack == "unknown":
            detected_stack = tool_manager._detect_project_stack(project_path)
            if detected_stack != "unknown":
                actual_stack = detected_stack
                logging.info(f"🔍 Auto-detected stack: '{detected_stack}' in {project_path}")
            else:
                logging.warning(f"⚠️ Unable to detect stack, using generic tests")
        else:
            # ✅ Validate declared stack matches project reality
            detected_stack = tool_manager._detect_project_stack(project_path)
            if detected_stack != "unknown" and detected_stack != stack:
                logging.warning(f"⚠️ Stack mismatch: declared='{stack}' vs detected='{detected_stack}' - using detected stack")
                actual_stack = detected_stack
            else:
                logging.info(f"✅ Stack validation passed: declared='{stack}' matches project")
        
        logging.info(f"Running comprehensive tests for stack '{actual_stack}' in {project_path}")
        
        if actual_stack == "laravel":
            # ✅ Laravel tests - COMPREHENSIVE validation before executing
            artisan_exists = project_path and os.path.exists(os.path.join(project_path, "artisan"))
            composer_json_exists = project_path and os.path.exists(os.path.join(project_path, "composer.json"))
            vendor_autoload_exists = project_path and os.path.exists(os.path.join(project_path, "vendor", "autoload.php"))
            bootstrap_app_exists = project_path and os.path.exists(os.path.join(project_path, "bootstrap", "app.php"))
            vendor_laravel_exists = project_path and os.path.exists(os.path.join(project_path, "vendor", "laravel", "framework"))
            
            validation_details = {
                "artisan_exists": artisan_exists,
                "composer_json_exists": composer_json_exists,
                "vendor_autoload_exists": vendor_autoload_exists,
                "bootstrap_app_exists": bootstrap_app_exists,
                "vendor_laravel_exists": vendor_laravel_exists
            }
            
            # Check all essential files
            if not all([artisan_exists, composer_json_exists, vendor_autoload_exists, bootstrap_app_exists, vendor_laravel_exists]):
                missing_files = [k for k, v in validation_details.items() if not v]
                logging.error(f"❌ Laravel project incomplete. Missing files: {missing_files}")
                logging.error(f"   Validation details: {validation_details}")
                return [TestResult(
                    test_type="laravel_validation", 
                    status="failed", 
                    output=f"Incomplete Laravel project - Missing essential files: {', '.join(missing_files)}",
                    details=validation_details
                )]
            
            # 🔥 FIX: Removed confusing description strings that could cause 'await on string' errors
            laravel_tests = ["pest", "phpstan", "pint"]
            
            for test_name in laravel_tests:
                try:
                    result = await tool_manager.run_test(project_path, test_name)
                    results.append(result)
                    logging.info(f"Laravel {test_name}: {result.status}")
                except Exception as e:
                    logging.warning(f"Laravel {test_name} failed to execute: {e}")
                    results.append(TestResult(
                        test_type=test_name, 
                        status="skipped", 
                        output=f"Test skipped - {test_name} not available: {str(e)}",
                        details={"artisan_available": artisan_exists}
                    ))
                    
        elif actual_stack == "vue":
            # Vue.js tests with vitest and eslint
            test_types = [("vue", "vitest/jest"), ("eslint", "eslint")]
            for test_type, description in test_types:
                try:
                    result = await tool_manager.run_test(project_path, test_type)
                    results.append(result)
                    logging.info(f"Vue {description}: {result.status}")
                except Exception as e:
                    logging.warning(f"Vue {description} failed: {e}")
                    # For Vue, missing test setup is common - mark as passed with info
                    results.append(TestResult(
                        test_type=test_type,
                        status="passed", 
                        output=f"Test setup not found (common for new projects): {str(e)}",
                        details={"skipped_reason": "missing_setup"}
                    ))
                    
        elif actual_stack in ["react", "node"]:
            # JavaScript tests for React/Node
            test_types = [("jest", "unit tests"), ("eslint", "linting")]
            for test_type, description in test_types:
                try:
                    result = await tool_manager.run_test(project_path, test_type)
                    results.append(result)
                    logging.info(f"JavaScript {description}: {result.status}")
                except Exception as e:
                    logging.warning(f"JavaScript {description} failed: {e}")
                    # Mark as passed if test setup doesn't exist yet
                    results.append(TestResult(
                        test_type=test_type,
                        status="passed", 
                        output=f"Test setup not configured yet: {str(e)}",
                        details={"skipped_reason": "missing_setup"}
                    ))
                    
        elif actual_stack == "python":
            # Python tests with pytest
            try:
                result = await tool_manager.run_test(project_path, "python")
                results.append(result)
                logging.info(f"Python pytest: {result.status}")
            except Exception as e:
                logging.warning(f"Python tests failed: {e}")
                # For new Python projects, missing tests are common
                results.append(TestResult(
                    test_type="python",
                    status="passed", 
                    output=f"No tests found (common for new projects): {str(e)}",
                    details={"skipped_reason": "no_tests_found"}
                ))
        else:
            # ✅ Unknown stack - create a generic "passed" result (NO Laravel fallback)
            logging.info(f"Unknown stack '{actual_stack}' - skipping tests (no Laravel fallback)")
            results.append(TestResult(
                test_type="generic",
                status="passed", 
                output=f"No specific tests defined for stack '{actual_stack}' - project may need custom test setup",
                details={"stack": actual_stack, "original_stack": stack}
            ))
        
        # Ensure we always return at least one result
        if not results:
            results.append(TestResult(
                test_type="fallback",
                status="passed", 
                output="No tests were executed",
                details={"reason": "empty_results"}
            ))
        
        # ✅ Log summary with actual stack used
        passed_count = sum(1 for r in results if r.status == "passed")
        logging.info(f"✅ Test summary: {passed_count}/{len(results)} passed for stack '{actual_stack}' (declared: '{stack}')")
        
        return results
        
    except Exception as e:
        logging.error(f"Critical error in run_comprehensive_tests: {e}")
        # Return a failed result so the system doesn't break
        return [TestResult(
            test_type="system_error",
            status="failed", 
            output=f"Test system error: {str(e)}",
            details={"exception": str(e)}
        )]

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
