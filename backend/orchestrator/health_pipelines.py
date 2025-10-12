"""
🔥 PHASE 3: Stack-Agnostic Health Pipelines
Run health checks (lint, tests, build, smoke) for different stacks.
"""

import os
import logging
import asyncio
from pathlib import Path
from typing import Dict, Any, List
import subprocess
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class HealthPipelineRunner:
    """
    Stack-agnostic health pipeline runner
    
    Supports:
    - Laravel: composer, pint, pest/phpunit, phpstan, smoke
    - Node: npm ci, eslint, jest/vitest, build, smoke
    - Python: pip, ruff/flake8, mypy, pytest, smoke
    - Generic: Git clean, README, encoding, file sizes
    """
    
    def __init__(self, timeout_seconds: int = 300):
        self.timeout = timeout_seconds
    
    async def run_health_pipeline(
        self, 
        project_path: str, 
        stack: str
    ) -> Dict[str, Any]:
        """
        🔥 PHASE 3: Run full health pipeline for a stack
        
        Returns:
            {
                "stack": str,
                "checks": [
                    {
                        "name": str,
                        "status": "passed" | "failed" | "skipped",
                        "output": str,
                        "duration_seconds": float
                    }
                ],
                "overall_status": "passed" | "failed",
                "ran_at": str
            }
        """
        try:
            if stack == "laravel":
                checks = await self._run_laravel_pipeline(project_path)
            elif stack == "node":
                checks = await self._run_node_pipeline(project_path)
            elif stack == "python":
                checks = await self._run_python_pipeline(project_path)
            else:
                checks = await self._run_generic_pipeline(project_path)
            
            # Determine overall status
            has_failures = any(c.get("status") == "failed" for c in checks)
            overall_status = "failed" if has_failures else "passed"
            
            return {
                "stack": stack,
                "checks": checks,
                "overall_status": overall_status,
                "ran_at": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ Health pipeline failed: {e}")
            return {
                "stack": stack,
                "checks": [],
                "overall_status": "failed",
                "error": str(e),
                "ran_at": datetime.now(timezone.utc).isoformat()
            }
    
    async def _run_laravel_pipeline(self, project_path: str) -> List[Dict[str, Any]]:
        """
        🔥 Laravel health pipeline:
        1. composer install
        2. pint (format)
        3. pest/phpunit (tests)
        4. phpstan (static analysis)
        5. smoke (artisan route:list)
        """
        checks = []
        
        # 1. Composer install
        checks.append(await self._run_command(
            name="composer_install",
            command=["composer", "install", "--no-interaction", "--prefer-dist"],
            cwd=project_path,
            description="Install dependencies"
        ))
        
        # 2. Pint (if available)
        if (Path(project_path) / "vendor/bin/pint").exists():
            checks.append(await self._run_command(
                name="pint_lint",
                command=["vendor/bin/pint", "--test"],
                cwd=project_path,
                description="Code formatting check"
            ))
        else:
            checks.append({
                "name": "pint_lint",
                "status": "skipped",
                "output": "Pint not found",
                "duration_seconds": 0
            })
        
        # 3. Pest/PHPUnit
        if (Path(project_path) / "vendor/bin/pest").exists():
            checks.append(await self._run_command(
                name="pest_tests",
                command=["vendor/bin/pest"],
                cwd=project_path,
                description="Run tests (Pest)"
            ))
        elif (Path(project_path) / "vendor/bin/phpunit").exists():
            checks.append(await self._run_command(
                name="phpunit_tests",
                command=["vendor/bin/phpunit"],
                cwd=project_path,
                description="Run tests (PHPUnit)"
            ))
        else:
            checks.append({
                "name": "tests",
                "status": "skipped",
                "output": "No test runner found",
                "duration_seconds": 0
            })
        
        # 4. PHPStan (if available)
        if (Path(project_path) / "vendor/bin/phpstan").exists():
            checks.append(await self._run_command(
                name="phpstan_analysis",
                command=["vendor/bin/phpstan", "analyse", "--no-progress"],
                cwd=project_path,
                description="Static analysis"
            ))
        else:
            checks.append({
                "name": "phpstan_analysis",
                "status": "skipped",
                "output": "PHPStan not found",
                "duration_seconds": 0
            })
        
        # 5. Smoke test (artisan)
        checks.append(await self._run_command(
            name="artisan_smoke",
            command=["php", "artisan", "route:list"],
            cwd=project_path,
            description="Artisan smoke test"
        ))
        
        return checks
    
    async def _run_node_pipeline(self, project_path: str) -> List[Dict[str, Any]]:
        """
        🔥 Node/JS health pipeline:
        1. npm ci
        2. eslint (if config exists)
        3. npm test (jest/vitest)
        4. npm run build (if script exists)
        5. smoke (optional)
        """
        checks = []
        
        # 1. npm ci
        checks.append(await self._run_command(
            name="npm_install",
            command=["npm", "ci"],
            cwd=project_path,
            description="Install dependencies"
        ))
        
        # 2. ESLint (if config exists)
        eslint_configs = [".eslintrc", ".eslintrc.json", ".eslintrc.js", "eslint.config.js"]
        has_eslint = any((Path(project_path) / cfg).exists() for cfg in eslint_configs)
        
        if has_eslint:
            checks.append(await self._run_command(
                name="eslint_lint",
                command=["npm", "run", "lint"],
                cwd=project_path,
                description="Linting"
            ))
        else:
            checks.append({
                "name": "eslint_lint",
                "status": "skipped",
                "output": "No ESLint config found",
                "duration_seconds": 0
            })
        
        # 3. npm test
        checks.append(await self._run_command(
            name="npm_test",
            command=["npm", "test", "--", "--watchAll=false"],
            cwd=project_path,
            description="Run tests"
        ))
        
        # 4. npm run build (if script exists)
        try:
            import json
            with open(Path(project_path) / "package.json") as f:
                package = json.load(f)
                if "build" in package.get("scripts", {}):
                    checks.append(await self._run_command(
                        name="npm_build",
                        command=["npm", "run", "build"],
                        cwd=project_path,
                        description="Build project"
                    ))
                else:
                    checks.append({
                        "name": "npm_build",
                        "status": "skipped",
                        "output": "No build script found",
                        "duration_seconds": 0
                    })
        except:
            checks.append({
                "name": "npm_build",
                "status": "skipped",
                "output": "Could not read package.json",
                "duration_seconds": 0
            })
        
        return checks
    
    async def _run_python_pipeline(self, project_path: str) -> List[Dict[str, Any]]:
        """
        🔥 Python health pipeline:
        1. pip install -r requirements.txt
        2. ruff/flake8 (if config exists)
        3. mypy (if config exists)
        4. pytest (if tests exist)
        5. smoke (optional)
        """
        checks = []
        
        # 1. pip install
        if (Path(project_path) / "requirements.txt").exists():
            checks.append(await self._run_command(
                name="pip_install",
                command=["pip", "install", "-r", "requirements.txt"],
                cwd=project_path,
                description="Install dependencies"
            ))
        else:
            checks.append({
                "name": "pip_install",
                "status": "skipped",
                "output": "No requirements.txt found",
                "duration_seconds": 0
            })
        
        # 2. Ruff (if available)
        ruff_config = (Path(project_path) / "ruff.toml")
        if ruff_config.exists():
            checks.append(await self._run_command(
                name="ruff_lint",
                command=["ruff", "check", "."],
                cwd=project_path,
                description="Linting (ruff)"
            ))
        else:
            checks.append({
                "name": "ruff_lint",
                "status": "skipped",
                "output": "No ruff config found",
                "duration_seconds": 0
            })
        
        # 3. mypy (if config exists)
        mypy_config = (Path(project_path) / "mypy.ini")
        if mypy_config.exists():
            checks.append(await self._run_command(
                name="mypy_typecheck",
                command=["mypy", "."],
                cwd=project_path,
                description="Type checking"
            ))
        else:
            checks.append({
                "name": "mypy_typecheck",
                "status": "skipped",
                "output": "No mypy config found",
                "duration_seconds": 0
            })
        
        # 4. pytest
        if (Path(project_path) / "tests").exists() or (Path(project_path) / "test").exists():
            checks.append(await self._run_command(
                name="pytest_tests",
                command=["pytest", "-q"],
                cwd=project_path,
                description="Run tests"
            ))
        else:
            checks.append({
                "name": "pytest_tests",
                "status": "skipped",
                "output": "No tests directory found",
                "duration_seconds": 0
            })
        
        return checks
    
    async def _run_generic_pipeline(self, project_path: str) -> List[Dict[str, Any]]:
        """
        🔥 Generic fallback pipeline:
        1. Git clean
        2. README exists
        3. No encoding errors
        4. File sizes OK
        """
        checks = []
        
        # 1. Git clean
        try:
            import git
            repo = git.Repo(project_path)
            is_clean = not repo.is_dirty(untracked_files=False)
            checks.append({
                "name": "git_clean",
                "status": "passed" if is_clean else "failed",
                "output": "Git working directory is clean" if is_clean else "Uncommitted changes detected",
                "duration_seconds": 0
            })
        except:
            checks.append({
                "name": "git_clean",
                "status": "skipped",
                "output": "Not a git repository",
                "duration_seconds": 0
            })
        
        # 2. README exists
        readme_exists = any(
            (Path(project_path) / name).exists() 
            for name in ["README.md", "README", "README.txt"]
        )
        checks.append({
            "name": "readme_exists",
            "status": "passed" if readme_exists else "failed",
            "output": "README found" if readme_exists else "README not found",
            "duration_seconds": 0
        })
        
        # 3. Check for large files
        large_files = []
        for file_path in Path(project_path).rglob("*"):
            if file_path.is_file():
                try:
                    size = file_path.stat().st_size
                    if size > 10 * 1024 * 1024:  # 10 MB
                        large_files.append(f"{file_path.name} ({size // 1024 // 1024} MB)")
                except:
                    pass
        
        if large_files:
            checks.append({
                "name": "file_sizes",
                "status": "failed",
                "output": f"Large files found: {', '.join(large_files[:5])}",
                "duration_seconds": 0
            })
        else:
            checks.append({
                "name": "file_sizes",
                "status": "passed",
                "output": "No files larger than 10 MB",
                "duration_seconds": 0
            })
        
        return checks
    
    async def _run_command(
        self, 
        name: str, 
        command: List[str], 
        cwd: str,
        description: str = ""
    ) -> Dict[str, Any]:
        """
        Run a command and capture output
        
        Returns:
            {
                "name": str,
                "status": "passed" | "failed",
                "output": str,
                "duration_seconds": float,
                "description": str
            }
        """
        start_time = datetime.now(timezone.utc)
        
        try:
            logger.info(f"🔧 Running {name}: {' '.join(command)}")
            
            process = await asyncio.create_subprocess_exec(
                *command,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), 
                    timeout=self.timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                return {
                    "name": name,
                    "status": "failed",
                    "output": f"Command timed out after {self.timeout}s",
                    "duration_seconds": self.timeout,
                    "description": description
                }
            
            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            
            output = (stdout + stderr).decode('utf-8', errors='replace')
            status = "passed" if process.returncode == 0 else "failed"
            
            logger.info(f"✅ {name}: {status} ({duration:.2f}s)")
            
            return {
                "name": name,
                "status": status,
                "output": output[:2000],  # Limit output size
                "return_code": process.returncode,
                "duration_seconds": round(duration, 2),
                "description": description
            }
            
        except Exception as e:
            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            logger.error(f"❌ {name} failed: {e}")
            
            return {
                "name": name,
                "status": "failed",
                "output": f"Exception: {str(e)}",
                "duration_seconds": round(duration, 2),
                "description": description
            }
