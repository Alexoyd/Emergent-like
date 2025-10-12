"""
🔥 PHASE 3: Auto-Heal Module
Automated project healing with stack-agnostic health pipelines.

Creates autofix/* branches, applies fixes, runs health checks, and tags branches
as ready-to-merge or needs-review. NEVER auto-merges to main.
"""

import os
import logging
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import git
import json

from .file_writer import execute_operations, FileWriterError
from .schemas import StepCommit

logger = logging.getLogger(__name__)


class AutoHealError(Exception):
    """Exception raised during auto-heal process"""
    pass


class AutoHealManager:
    """
    Manages auto-heal workflow:
    1. Create autofix/* branch
    2. Detect stack
    3. Apply fixes (LLM or no-LLM)
    4. Run health pipelines
    5. Tag branch (ready-to-merge / needs-review)
    """
    
    def __init__(self, health_pipeline_runner):
        self.health_runner = health_pipeline_runner
    
    async def start_auto_heal(
        self,
        project_id: str,
        project_path: str,
        max_steps: int = 5,
        branch_name: Optional[str] = None,
        auto_merge: bool = False,
        operations: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        🔥 PHASE 3: Start auto-heal process
        
        Args:
            project_id: Project ID
            project_path: Path to project code
            max_steps: Maximum fix steps (default: 5)
            branch_name: Custom branch name (default: autofix/YYYYMMDD-HHMMSS)
            auto_merge: Auto-merge to main (ALWAYS FALSE, for future)
            operations: Optional no-LLM operations injection
            
        Returns:
            {
                "branch_name": str,
                "branch_commit": str,
                "steps_applied": int,
                "health_status": "ready-to-merge" | "needs-review",
                "artifacts": {...}
            }
        """
        try:
            # Validate project path
            project_path_obj = Path(project_path)
            if not project_path_obj.exists():
                raise AutoHealError(f"Project path not found: {project_path}")
            
            # Initialize Git repo
            try:
                repo = git.Repo(project_path)
            except git.InvalidGitRepositoryError:
                repo = git.Repo.init(project_path)
                logger.info(f"✅ Initialized Git repository at {project_path}")
            
            # Ensure clean state
            if repo.is_dirty(untracked_files=True):
                logger.warning("⚠️ Project has uncommitted changes. Committing before auto-heal...")
                repo.git.add(A=True)
                repo.index.commit(f"Pre-auto-heal commit for project {project_id}")
            
            # Create autofix branch
            if not branch_name:
                timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
                branch_name = f"autofix/{timestamp}"
            
            # Create and checkout branch from HEAD
            logger.info(f"🌿 Creating branch {branch_name} from HEAD")
            current_branch = repo.active_branch.name
            new_branch = repo.create_head(branch_name)
            new_branch.checkout()
            
            branch_commit = repo.head.commit.hexsha
            logger.info(f"✅ Created branch {branch_name} at {branch_commit[:8]}")
            
            # Detect stack
            stack = await self._detect_stack(project_path_obj)
            logger.info(f"🔍 Detected stack: {stack}")
            
            # Apply fixes
            steps_applied = 0
            files_changed = []
            
            if operations:
                # No-LLM path: apply provided operations
                logger.info(f"🔧 Applying {len(operations)} no-LLM operations")
                
                try:
                    exec_results = await execute_operations(
                        operations,
                        str(project_path),
                        project_id
                    )
                except FileWriterError as e:
                    # Protected paths and validation errors
                    logger.error(f"🛡️ File operation validation failed: {str(e)}")
                    raise  # Propagate to endpoint for HTTP 422
                
                # Check for failures
                failed_ops = [r for r in exec_results if r.get("status") == "failed"]
                if failed_ops:
                    errors = "; ".join([f"{r.get('operation_type')}: {r.get('error')}" for r in failed_ops])
                    logger.error(f"❌ Operations failed: {errors}")
                else:
                    files_changed = [r.get("path") for r in exec_results if r.get("path")]
                    steps_applied = len(exec_results)
                    
                    # Commit changes
                    if files_changed:
                        commit_msg = StepCommit(
                            run_id=f"autoheal-{project_id}",
                            step_number=1,
                            step_title="Auto-heal fixes applied"
                        ).format_message().replace("feat(", "fix(autofix:")
                        
                        repo.git.add(A=True)
                        repo.index.commit(commit_msg)
                        logger.info(f"✅ Committed changes: {commit_msg}")
            else:
                # LLM path would go here (not implemented yet)
                logger.warning("⚠️ No operations provided and LLM path not implemented")
            
            # Run health pipelines
            logger.info(f"🏥 Running health pipelines for stack: {stack}")
            health_results = await self.health_runner.run_health_pipeline(
                project_path=str(project_path),
                stack=stack
            )
            
            # Determine health status
            all_passed = all(
                result.get("status") == "passed" 
                for result in health_results.get("checks", [])
            )
            health_status = "ready-to-merge" if all_passed else "needs-review"
            
            logger.info(f"✅ Health status: {health_status}")
            
            # Tag branch with status
            await self._tag_branch(repo, branch_name, health_status, health_results)
            
            # Return to original branch
            repo.heads[current_branch].checkout()
            
            return {
                "branch_name": branch_name,
                "branch_commit": repo.heads[branch_name].commit.hexsha,
                "steps_applied": steps_applied,
                "files_changed": files_changed,
                "health_status": health_status,
                "health_results": health_results,
                "stack": stack,
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ Auto-heal failed: {e}")
            # Try to return to original branch
            try:
                if 'repo' in locals() and 'current_branch' in locals():
                    repo.heads[current_branch].checkout()
            except:
                pass
            raise AutoHealError(f"Auto-heal failed: {str(e)}")
    
    async def _detect_stack(self, project_path: Path) -> str:
        """
        🔥 PHASE 3: Detect project stack via heuristics
        
        Returns: "laravel" | "node" | "python" | "generic"
        """
        # Laravel detection
        if (project_path / "composer.json").exists():
            try:
                with open(project_path / "composer.json") as f:
                    composer = json.load(f)
                    if "laravel/framework" in composer.get("require", {}):
                        return "laravel"
            except:
                pass
            # Also check for artisan
            if (project_path / "artisan").exists():
                return "laravel"
        
        # Node/JS detection
        if (project_path / "package.json").exists():
            return "node"
        
        # Python detection
        if (project_path / "pyproject.toml").exists() or (project_path / "requirements.txt").exists():
            return "python"
        
        # Fallback
        logger.warning("⚠️ Unable to detect stack, using generic fallback")
        return "generic"
    
    async def _tag_branch(
        self, 
        repo: git.Repo, 
        branch_name: str, 
        status: str,
        health_results: Dict[str, Any]
    ):
        """
        🔥 PHASE 3: Tag branch with health status
        
        Creates a JSON file in .git/autofix-status/{branch_name}.json
        """
        try:
            status_dir = Path(repo.working_dir) / ".git" / "autofix-status"
            status_dir.mkdir(parents=True, exist_ok=True)
            
            status_file = status_dir / f"{branch_name.replace('/', '_')}.json"
            status_data = {
                "branch": branch_name,
                "status": status,
                "health_results": health_results,
                "tagged_at": datetime.now(timezone.utc).isoformat()
            }
            
            with open(status_file, 'w') as f:
                json.dump(status_data, f, indent=2)
            
            logger.info(f"✅ Tagged branch {branch_name} as {status}")
            
        except Exception as e:
            logger.warning(f"⚠️ Failed to tag branch: {e}")
    
    async def get_branches(self, project_path: str) -> List[Dict[str, Any]]:
        """
        🔥 PHASE 3: Get all autofix branches with statuses
        
        Returns: List of {branch_name, status, last_commit, ...}
        """
        try:
            repo = git.Repo(project_path)
            status_dir = Path(project_path) / ".git" / "autofix-status"
            
            branches = []
            for branch in repo.heads:
                if branch.name.startswith("autofix/"):
                    # Load status if exists
                    status_file = status_dir / f"{branch.name.replace('/', '_')}.json"
                    status_data = None
                    if status_file.exists():
                        try:
                            with open(status_file) as f:
                                status_data = json.load(f)
                        except:
                            pass
                    
                    branches.append({
                        "branch_name": branch.name,
                        "commit": branch.commit.hexsha,
                        "commit_message": branch.commit.message.strip(),
                        "author": str(branch.commit.author),
                        "committed_at": branch.commit.committed_datetime.isoformat(),
                        "status": status_data.get("status") if status_data else "unknown",
                        "health_results": status_data.get("health_results") if status_data else None
                    })
            
            return branches
            
        except Exception as e:
            logger.error(f"❌ Failed to get branches: {e}")
            return []
    
    async def get_branch_artifacts(
        self, 
        project_path: str, 
        branch_name: str
    ) -> Dict[str, Any]:
        """
        🔥 PHASE 3: Get artifacts for a specific branch
        
        Returns: {diffs, files_changed, logs, health_results}
        """
        try:
            repo = git.Repo(project_path)
            
            # Get branch
            if branch_name not in [b.name for b in repo.heads]:
                raise ValueError(f"Branch {branch_name} not found")
            
            branch = repo.heads[branch_name]
            
            # Get diff from branch point to branch head
            # Find merge base with main/master
            main_branch = None
            for name in ['main', 'master']:
                if name in [b.name for b in repo.heads]:
                    main_branch = repo.heads[name]
                    break
            
            if main_branch:
                merge_base = repo.merge_base(main_branch, branch)[0]
                diff = repo.git.diff(merge_base, branch)
            else:
                # No main branch, just show branch commits
                diff = repo.git.show(branch.commit)
            
            # Get commits
            commits = []
            for commit in repo.iter_commits(branch, max_count=10):
                commits.append({
                    "hash": commit.hexsha,
                    "message": commit.message.strip(),
                    "author": str(commit.author),
                    "date": commit.committed_datetime.isoformat()
                })
            
            # Get status
            status_dir = Path(project_path) / ".git" / "autofix-status"
            status_file = status_dir / f"{branch_name.replace('/', '_')}.json"
            status_data = None
            if status_file.exists():
                try:
                    with open(status_file) as f:
                        status_data = json.load(f)
                except:
                    pass
            
            return {
                "branch_name": branch_name,
                "diff": diff,
                "commits": commits,
                "status": status_data.get("status") if status_data else "unknown",
                "health_results": status_data.get("health_results") if status_data else None,
                "retrieved_at": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to get branch artifacts: {e}")
            raise
    
    async def close_branch(self, project_path: str, branch_name: str) -> bool:
        """
        🔥 PHASE 3: Close/cleanup autofix branch
        
        Deletes branch and status file
        """
        try:
            repo = git.Repo(project_path)
            
            # Ensure not on this branch
            if repo.active_branch.name == branch_name:
                # Switch to main/master
                for name in ['main', 'master']:
                    if name in [b.name for b in repo.heads]:
                        repo.heads[name].checkout()
                        break
            
            # Delete branch
            if branch_name in [b.name for b in repo.heads]:
                repo.delete_head(branch_name, force=True)
                logger.info(f"✅ Deleted branch {branch_name}")
            
            # Delete status file
            status_dir = Path(project_path) / ".git" / "autofix-status"
            status_file = status_dir / f"{branch_name.replace('/', '_')}.json"
            if status_file.exists():
                status_file.unlink()
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to close branch: {e}")
            return False
