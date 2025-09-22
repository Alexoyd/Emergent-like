import os
import logging
import asyncio
import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import Optional, Dict, Any, List
import git
from dataclasses import dataclass

logger = logging.getLogger(__name__)

def is_valid_patch(patch_text: str) -> bool:
    """
    Validate patch format before applying
    Returns True if patch appears to be valid unified diff format
    """
    if not patch_text or not patch_text.strip():
        logger.warning("Patch validation failed: empty patch")
        return False
    
    lines = patch_text.strip().split(\'\
\')
    
    # Check if patch starts with proper diff header
    if not lines[0].startswith("diff --git"):
        logger.warning("Patch validation failed: missing \'diff --git\' header")
        return False
    
    # Check for required file headers
    has_old_file = False
    has_new_file = False
    
    for line in lines:
        if line.startswith("--- "):
            has_old_file = True
        elif line.startswith("+++ "):
            has_new_file = True
            
    if not has_old_file or not has_new_file:
        logger.warning("Patch validation failed: missing \'---\' or \'+++\' file headers")
        return False
    
    # Check for basic patch structure (should have at least one hunk)
    has_hunk_header = False
    for line in lines:
        if line.startswith("@@") and "@@" in line[2:]:
            has_hunk_header = True
            break
            
    if not has_hunk_header:
        logger.warning("Patch validation failed: missing hunk headers \'@@\'")
        return False
    
    # Additional format checks
    for i, line in enumerate(lines, 1):
        # Skip headers and hunk headers
        if (line.startswith(("diff --git", "index ", "--- ", "+++ ", "@@")) or 
            line.startswith(("new file", "deleted file", "similarity"))):
            continue
            
        # Check that patch lines start with valid prefixes
        if line and not line.startswith((" ", "+", "-")):
            # Allow empty lines in patches
            if line.strip():
                logger.warning(f"Patch validation failed: invalid line format at line {i}: \'{line[:50]}...\'")
                return False
    
    return True
@dataclass
class TestResult:
    test_type: str
    status: str  # "passed" or "failed"
    output: str
    details: Optional[Dict[str, Any]] = None

class ToolManager:
    def __init__(self):
        self.timeout = 300  # 5 minutes default timeout
    
    async def read_file(self, file_path: str) -> str:
        """Read file content"""
        try:
            path = Path(file_path)
            if not path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")
            
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
                
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")
            raise
    
    async def write_file(self, file_path: str, content: str) -> bool:
        """Write content to file"""
        try:
            path = Path(file_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            return True
            
        except Exception as e:
            logger.error(f"Error writing file {file_path}: {e}")
            return False
    
    async def apply_patch(self, patch: str, project_path: Optional[str] = None) -> bool:
        """Apply unified diff patch with pre-validation"""
        try:
            if not project_path:
                project_path = os.getcwd()
                
             # ✅ Validate patch format BEFORE applying
            if not is_valid_patch(patch):
                logger.error("Patch validation failed: Invalid patch format. Please provide a valid unified diff patch.")
                return False
            
            # Create temporary patch file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.patch', delete=False) as f:
                f.write(patch)
                patch_file = f.name
            
            try:
                # Apply patch using git apply
                result = await self._run_command(
                    ["git", "apply", "--check", patch_file],
                    cwd=project_path
                )
                
                if result.returncode == 0:
                    # Patch is valid, apply it
                    result = await self._run_command(
                        ["git", "apply", patch_file],
                        cwd=project_path
                    )
                    return result.returncode == 0
                else:
                    logger.warning(f"Git patch validation failed: {result.stderr}")
                    logger.error("Unable to apply patch. Please provide a valid patch that can be applied.")
                    return False
                    
            finally:
                os.unlink(patch_file)
                
        except Exception as e:
            logger.error(f"Error applying patch: {e}")
            return False
    
    async def run_command(self, command: List[str], cwd: Optional[str] = None) -> TestResult:
        """Run shell command and return result"""
        try:
            result = await self._run_command(command, cwd)
            
            return TestResult(
                test_type="command",
                status="passed" if result.returncode == 0 else "failed",
                output=f"STDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}",
                details={
                    "command": " ".join(command),
                    "return_code": result.returncode,
                    "cwd": cwd
                }
            )
            
        except Exception as e:
            logger.error(f"Error running command {' '.join(command)}: {e}")
            return TestResult(
                test_type="command",
                status="failed",
                output=f"Error: {str(e)}",
                details={"command": " ".join(command), "error": str(e)}
            )
    
    async def run_test(self, project_path: Optional[str], test_type: str) -> TestResult:
        """Run specific test type"""
        try:
            if not project_path:
                project_path = os.getcwd()
            
            commands = self._get_test_commands(test_type)
            if not commands:
                return TestResult(
                    test_type=test_type,
                    status="failed",
                    output=f"Unknown test type: {test_type}"
                )
            
            for command in commands:
                result = await self._run_command(command, cwd=project_path)
                
                if result.returncode != 0:
                    return TestResult(
                        test_type=test_type,
                        status="failed",
                        output=f"Command failed: {' '.join(command)}\n\nSTDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}",
                        details={
                            "command": " ".join(command),
                            "return_code": result.returncode
                        }
                    )
            
            return TestResult(
                test_type=test_type,
                status="passed",
                output=f"All {test_type} tests passed",
                details={"commands_run": len(commands)}
            )
            
        except Exception as e:
            logger.error(f"Error running {test_type} tests: {e}")
            return TestResult(
                test_type=test_type,
                status="failed",
                output=f"Error: {str(e)}"
            )
    
    def _get_test_commands(self, test_type: str) -> List[List[str]]:
        """Get commands for specific test type"""
        commands_map = {
            "pest": [["php", "artisan", "test"]],
            "phpstan": [["./vendor/bin/phpstan", "analyse"]],
            "pint": [["./vendor/bin/pint", "--test"]],
            "jest": [["npm", "test"]],
            "eslint": [["npm", "run", "lint"]],
            "playwright": [["npx", "playwright", "test"]],
            "composer": [["composer", "test"]],
            "npm": [["npm", "test"]]
        }
        
        return commands_map.get(test_type, [])
    
    async def _run_command(self, command: List[str], cwd: Optional[str] = None):
        """Run command with timeout"""
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=self.timeout
            )
            
            return type('CommandResult', (), {
                'returncode': process.returncode,
                'stdout': stdout.decode('utf-8', errors='ignore'),
                'stderr': stderr.decode('utf-8', errors='ignore')
            })()
            
        except asyncio.TimeoutError:
            logger.error(f"Command timeout: {' '.join(command)}")
            if 'process' in locals():
                process.kill()
                await process.wait()
            raise Exception(f"Command timed out after {self.timeout} seconds")
    
    async def init_git_repo(self, project_path: str) -> bool:
        """Initialize git repository"""
        try:
            repo_path = Path(project_path)
            if (repo_path / '.git').exists():
                return True
            
            result = await self._run_command(["git", "init"], cwd=project_path)
            return result.returncode == 0
            
        except Exception as e:
            logger.error(f"Error initializing git repo: {e}")
            return False
    
    async def commit_changes(self, project_path: str, message: str) -> bool:
        """Commit changes to git"""
        try:
            # Add all changes
            result = await self._run_command(["git", "add", "."], cwd=project_path)
            if result.returncode != 0:
                return False
            
            # Commit changes
            result = await self._run_command(
                ["git", "commit", "-m", message],
                cwd=project_path
            )
            return result.returncode == 0
            
        except Exception as e:
            logger.error(f"Error committing changes: {e}")
            return False
    
    async def create_pull_request(self, project_path: str, branch: str, title: str, description: str) -> bool:
        """Create pull request (simplified version)"""
        try:
            # Create and switch to new branch
            result = await self._run_command(
                ["git", "checkout", "-b", branch],
                cwd=project_path
            )
            if result.returncode != 0:
                return False
            
            # Commit would already be done by commit_changes
            
            # Push branch (assumes remote is configured)
            result = await self._run_command(
                ["git", "push", "origin", branch],
                cwd=project_path
            )
            
            # Note: Actual PR creation would require GitHub/GitLab API integration
            logger.info(f"Branch {branch} pushed. Manual PR creation required.")
            return result.returncode == 0
            
        except Exception as e:
            logger.error(f"Error creating pull request: {e}")
            return False
    
    async def check_file_exists(self, file_path: str) -> bool:
        """Check if file exists"""
        return Path(file_path).exists()
    
    async def list_files(self, directory: str, pattern: str = "*") -> List[str]:
        """List files in directory matching pattern"""
        try:
            path = Path(directory)
            if not path.exists():
                return []
            
            return [str(f) for f in path.rglob(pattern) if f.is_file()]
            
        except Exception as e:
            logger.error(f"Error listing files: {e}")
            return []
    
    async def backup_file(self, file_path: str) -> str:
        """Create backup of file"""
        try:
            path = Path(file_path)
            backup_path = path.with_suffix(path.suffix + '.backup')
            
            shutil.copy2(path, backup_path)
            return str(backup_path)
            
        except Exception as e:
            logger.error(f"Error backing up file: {e}")
            raise
