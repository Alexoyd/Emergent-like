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
from backend.orchestrator.llm_router import LLMRouter
from backend.orchestrator.tools import ToolManager
from backend.orchestrator.state_manager import StateManager
from backend.orchestrator.rag_system import RAGSystem
from backend.orchestrator.project_manager import ProjectManager
from backend.orchestrator.github_integration import GitHubIntegration
from backend.orchestrator.plan_parser import parse_plan

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
project_manager = ProjectManager()
github_integration = GitHubIntegration()

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
    """Create a new AI agent run with project isolation"""
    try:
        # Create run record
        run = Run(**run_data.dict())
        
        # Create isolated project workspace
        project_workspace = await project_manager.create_project_workspace(
            project_id=run.id,
            stack=run.stack,
            project_name=f"Run {run.id[:8]}"
        )
        
        # Update run with project path
        run.project_path = project_workspace["code_path"]
        
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
            await state_manager.add_log(run_id, {"step": "plan", "status": "succeeded", "output": plan})

            # 🆕 Parse du plan et enregistrement dans la base
            parsed_steps = parse_plan(plan)
            await db.runs.update_one(
                {"id": run_id},
                {"$set": {"plan": plan, "parsed_plan": parsed_steps}}
            )
        
        # Execute steps
        current_step = from_step
        steps_executed = 0
        completed_successfully = True
        
        await state_manager.add_log(run_id, {"type": "info", "content": f"Starting execution from step {current_step}"})
        
        while current_step < run.max_steps:
            try:
                # Check if run was cancelled
                run_data = await db.runs.find_one({"id": run_id})
                if not run_data or Run(**run_data).status == RunStatus.CANCELLED:
                    await state_manager.add_log(run_id, {"type": "warning", "content": "Run was cancelled"})
                    completed_successfully = False
                    break
                
                await state_manager.add_log(run_id, {"type": "info", "content": f"Executing step {current_step + 1}/{run.max_steps}"})

                # Execute step
                step_result = await execute_step(run_id, current_step)
                steps_executed += 1

                # Check if step failed and needs retry
                if not step_result.tests_passed and step_result.retries < step_result.max_retries:
                    # Retry with higher model
                    await state_manager.add_log(run_id, {"type": "warning", "content": f"Step {current_step + 1} failed, retrying with escalation (attempt {step_result.retries + 1})"})
                    await retry_step_with_escalation(run_id, current_step, step_result.retries + 1)
                    continue
                elif not step_result.tests_passed:
                    # Max retries reached, fail the run
                    await state_manager.add_log(run_id, {"type": "error", "content": f"Step {current_step + 1} failed after {step_result.max_retries} retries"})
                    await state_manager.update_run_status(run_id, RunStatus.FAILED)
                    completed_successfully = False
                    break
                
                await state_manager.add_log(run_id, {"type": "success", "content": f"Step {current_step + 1} completed successfully"})
                current_step += 1
                # Update current step in database for progress tracking
                await state_manager.update_current_step(run_id, current_step)
                
                # Check budget limit
                run_data = await db.runs.find_one({"id": run_id})
                if run_data and Run(**run_data).cost_used_eur >= run.daily_budget_eur:
                    #await state_manager.add_log(run_id, {"step": "budget", "status": "failed", "output": "Daily budget limit reached"})
                    await state_manager.add_log(run_id, {"type": "warning", "content": "Daily budget limit reached, stopping execution"})
                    completed_successfully = False
                    break
                
            except Exception as e:
                logging.error(f"Error executing step {current_step}: {e}")
                #await state_manager.add_log(run_id, {"step": f"step {current_step}", "status": "failed", "output": f"Step {current_step} failed: {str(e)}"})
                await state_manager.add_log(run_id, {"type": "error", "content": f"Step {current_step + 1} failed with exception: {str(e)}"})
                completed_successfully = False
                break
        
        # Mark as completed if all steps successful
        #if current_step >= run.max_steps or current_step == 0:
        # Determine final status based on execution results
        if completed_successfully and steps_executed > 0:
            # ✅ PRIORITÉ 1 - Vérification des fichiers générés avant de marquer comme completed
            project_code_path = project_manager.get_code_path(run_id)
            if not await verify_code_files_generated(project_code_path, run.stack):
                await state_manager.add_log(run_id, {"type": "error", "content": f"Run completed but no code files were generated in {project_code_path}"})
                await state_manager.update_run_status(run_id, RunStatus.FAILED)
            else:
                await state_manager.add_log(run_id, {"type": "success", "content": f"All {steps_executed} steps completed successfully with code files generated"}) 
                await state_manager.update_run_status(run_id, RunStatus.COMPLETED)
        elif steps_executed == 0 and from_step == 0:
            # Only planning was done, no steps executed - this shouldn't mark as completed
            await state_manager.add_log(run_id, {"type": "error", "content": "No steps were executed after planning phase"})
            await state_manager.update_run_status(run_id, RunStatus.FAILED)
        elif not completed_successfully:
            # Steps were executed but run failed
            await state_manager.add_log(run_id, {"type": "info", "content": f"Run terminated after {steps_executed} steps"})
            # Status already set to FAILED in the loop if needed
        else:
            # Reached max steps
            # ✅ PRIORITÉ 1 - Vérification des fichiers même quand max steps atteint
            project_code_path = project_manager.get_code_path(run_id)
            if not await verify_code_files_generated(project_code_path, run.stack):
                await state_manager.add_log(run_id, {"type": "error", "content": f"Reached maximum steps but no code files were generated in {project_code_path}"})
                await state_manager.update_run_status(run_id, RunStatus.FAILED)
            else:
                await state_manager.add_log(run_id, {"type": "info", "content": f"Reached maximum steps limit ({run.max_steps}) with code files generated"})
                await state_manager.update_run_status(run_id, RunStatus.COMPLETED)
        
    except Exception as e:
        logging.error(f"Error executing run {run_id}: {e}")
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
            "python": ["main.py", "requirements.txt"],
            "node": ["package.json", "index.js"],
            "nodejs": ["package.json", "index.js"]
        }
        
        stack_lower = stack.lower() if stack else "unknown"
        required_files = expected_files.get(stack_lower, ["main.py"])  # Fallback to Python
        
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
