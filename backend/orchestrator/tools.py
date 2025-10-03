import os
import re
import logging
import asyncio
import subprocess
import tempfile
import shutil
import time  # ✅ PRIORITÉ 4 - Ajout import time manquant
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
    
    #lines = patch_text.strip().split('\#')
    lines = patch_text.strip().split("\n")

    # Check if patch starts with proper diff header
    if not lines[0].startswith("diff --git"):
        logger.warning("Patch validation failed: missing 'diff --git' header")
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
        logger.warning("Patch validation failed: missing '---' or '+++' file headers")
        return False
    
    # Check for basic patch structure (should have at least one hunk)
    has_hunk_header = False
    for line in lines:
        if line.startswith("@@") and "@@" in line[2:]:
            has_hunk_header = True
            break
            
    if not has_hunk_header:
        logger.warning("Patch validation failed: missing hunk headers '@@'")
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
                logger.warning(f"Patch validation failed: invalid line format at line {i}: '{line[:50]}...'")
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
    
    def _normalize_patch(self, patch: str, project_path: str) -> str:
        """
        Normalize patch paths to be repo-relative and fix line endings.
        Ensures paths are relative to project root for proper git application.
        """
        try:
            code_root = os.path.abspath(project_path)
            normalized_lines = []

            for line in patch.splitlines():
                if line.startswith(("---", "+++")):
                    # Handle file path lines
                    parts = line.split(" ", 1)
                    if len(parts) >= 2:
                        prefix, path_part = parts[0], parts[1]
                        
                        # Remove absolute path prefix if present
                        if code_root in path_part:
                            # Remove absolute prefix, keep relative path
                            relative_path = path_part.replace(code_root + "/", "")
                            # Ensure it doesn't start with / 
                            if relative_path.startswith("/"):
                                relative_path = relative_path[1:]
                            path_part = relative_path
                        
                        # Handle a/ and b/ prefixes properly
                        if not path_part.startswith(("a/", "b/")) and not path_part in ["/dev/null"]:
                            if prefix == "---":
                                path_part = f"a/{path_part}" if path_part != "/dev/null" else path_part
                            elif prefix == "+++":
                                path_part = f"b/{path_part}" if path_part != "/dev/null" else path_part
                        
                        normalized_lines.append(f"{prefix} {path_part}")
                    else:
                        # Malformed line, keep as-is
                        normalized_lines.append(line)
                else:
                    # Content lines, hunks, diff headers - keep unchanged
                    normalized_lines.append(line)
            
            # Join with proper line endings
            text = "\n".join(normalized_lines)
            
            # Normalize line endings (CRLF/CR -> LF)
            text = text.replace("\r\n", "\n").replace("\r", "\n")
            
            return text
            
        except Exception as e:
            logger.warning(f"Error normalizing patch: {e}")
            # Return original patch if normalization fails
            return patch.replace("\r\n", "\n").replace("\r", "\n")


    async def apply_patch(self, patch: str, project_path: Optional[str] = None) -> bool:
        """Apply unified diff patch with enhanced validation and error handling"""
        try:
            if not project_path:
                project_path = os.getcwd()
                
            logger.info(f"Applying patch to project: {project_path}")
            logger.debug(f"Patch content (first 200 chars): {patch[:200]}...")
            
            # ✅ Validate patch format BEFORE applying
            if not is_valid_patch(patch):
                logger.error("Patch validation failed: Invalid patch format. Please provide a valid unified diff patch.")
                return False
            
            # ✅ Check if project path exists and is a git repository
            if not os.path.exists(project_path):
                logger.error(f"Project path does not exist: {project_path}")
                return False
                
            # Initialize git repo if needed
            git_dir = os.path.join(project_path, '.git')
            if not os.path.exists(git_dir):
                logger.info(f"Initializing git repository in {project_path}")
                init_result = await self._run_command(["git", "init"], cwd=project_path)
                if init_result.returncode != 0:
                    logger.warning(f"Failed to initialize git repo: {init_result.stderr}")
            
            # ✅ Normalize patch and ensure final newline
            normalized_patch = self._normalize_patch(patch, project_path)
            appended_final_newline = False
            
            if not normalized_patch.endswith('\n'):
                normalized_patch += '\n'
                appended_final_newline = True
                logger.info("apply_patch: appended final newline")
            
            # ✅ Save debug copy to /tmp/emergent_patches
            timestamp = time.time()
            debug_dir = "/tmp/emergent_patches"
            debug_path = f"{debug_dir}/patch_{timestamp:.0f}.diff"
            
            try:
                os.makedirs(debug_dir, exist_ok=True)
                with open(debug_path, 'w', encoding='utf-8') as f:
                    f.write(normalized_patch)
                logger.info(f"Saved patch debug copy to {debug_path}")
            except Exception as e:
                logger.warning(f"Failed to save debug patch copy: {e}")
            
            # Create temporary patch file with normalized content
            with tempfile.NamedTemporaryFile(mode='w', suffix='.patch', delete=False, encoding='utf-8') as f:
                f.write(normalized_patch)
                patch_file = f.name
            
            try:
                # ✅ First check if patch can be applied cleanly
                check_result = await self._run_command(
                    ["git", "apply", "--check", patch_file],
                    cwd=project_path
                )
                
                if check_result.returncode == 0:
                    # Patch can be applied cleanly
                    apply_result = await self._run_command(
                        ["git", "apply", patch_file],
                        cwd=project_path
                    )
                                      
                    if apply_result.returncode == 0:
                        logger.info(f"✅ Patch applied successfully (final_newline={appended_final_newline})")
                        return True
                    else:
                        logger.error(f"❌ Git apply failed: {apply_result.stderr}")
                        self._log_patch_failure_details(normalized_patch, apply_result.stderr, "git_apply_failed")
                        return False
                else:
                    # Try applying with --3way for better conflict resolution
                    logger.warning(f"Patch check failed, trying 3-way merge: {check_result.stderr}")
                    
                    threeway_result = await self._run_command(
                        ["git", "apply", "--3way", patch_file],
                        cwd=project_path
                    )
                    
                    if threeway_result.returncode == 0:
                        logger.info("✅ Patch applied with 3-way merge")
                        return True
                    else:
                        logger.error(f"❌ Git 3-way apply failed: {threeway_result.stderr}")
                        self._log_patch_failure_details(normalized_patch, check_result.stderr, "git_check_and_3way_failed")
                        return False
                    
            finally:
                # Clean up temporary file
                try:
                    os.unlink(patch_file)
                except:
                    pass
                
        except Exception as e:
            logger.error(f"Critical error applying patch: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False
        
    def _log_patch_failure_details(self, patch: str, git_stderr: str, reason: str):
        """Log detailed information about patch application failure"""
        try:
            patch_lines = patch.split('')
            first_20_lines = ''.join(patch_lines[:20])
            
            logger.error(f"""
=== PATCH APPLICATION FAILURE ===
Reason: {reason}
First 20 lines of patch:
{first_20_lines}

Git stderr (complete):
{git_stderr}

Patch length: {len(patch)} characters
Patch lines: {len(patch_lines)}
=== END FAILURE DETAILS ===
            """.strip())
            
            # Try to identify specific line causing issue if possible
            if "corrupt patch at line" in git_stderr:
                import re
                match = re.search(r"corrupt patch at line (\d+)", git_stderr)
                if match:
                    line_num = int(match.group(1))
                    if line_num <= len(patch_lines):
                        faulty_line = patch_lines[line_num - 1] if line_num > 0 else "N/A"
                        logger.error(f"Faulty line {line_num}: '{faulty_line}'")
                        
        except Exception as e:
            logger.error(f"Failed to log patch failure details: {e}")
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
        """
        Run specific test type with multiple command fallbacks.
        Tries each command option until one succeeds or all fail.
        """
        try:
            if not project_path:
                project_path = os.getcwd()
            
            if not os.path.exists(project_path):
                return TestResult(
                    test_type=test_type,
                    status="failed",
                    output=f"Project path does not exist: {project_path}"
                )
            
            commands = self._get_test_commands(test_type)
            if not commands:
                return TestResult(
                    test_type=test_type,
                    status="failed",
                    output=f"No commands defined for test type: {test_type}"
                )
            
            last_error = None
            commands_tried = []
            
            # Try each command until one succeeds
            for command in commands:
                try:
                    logger.info(f"Trying {test_type} command: {' '.join(command)}")
                    result = await self._run_command(command, cwd=project_path)
                    commands_tried.append(' '.join(command))
                    
                    if result.returncode == 0:
                        # Success!
                        return TestResult(
                            test_type=test_type,
                            status="passed",
                            output=f"✅ {test_type} tests passed\n\nCommand: {' '.join(command)}\nOutput:\n{result.stdout}",
                            details={
                                "command": " ".join(command),
                                "return_code": result.returncode,
                                "commands_tried": commands_tried
                            }
                        )
                    else:
                        # Command failed, try next one
                        last_error = f"Command '{' '.join(command)}' failed (exit {result.returncode})\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
                        logger.warning(f"{test_type} command failed, trying next: {last_error[:200]}...")
                        continue
                        
                except FileNotFoundError:
                    # Command not found, try next one
                    last_error = f"Command '{' '.join(command)}' not found"
                    logger.info(f"{test_type} command not found: {' '.join(command)}")
                    commands_tried.append(' '.join(command) + " (not found)")
                    continue
                    
                except Exception as e:
                    # Other error, try next command
                    last_error = f"Command '{' '.join(command)}' error: {str(e)}"
                    logger.warning(f"{test_type} command error: {e}")
                    commands_tried.append(' '.join(command) + f" (error: {e})")
                    continue
            
            # All commands failed
            return TestResult(
                test_type=test_type,
                status="failed",
                output=f"❌ All {test_type} commands failed\n\nCommands tried:\n" + 
                       "\n".join(f"- {cmd}" for cmd in commands_tried) + 
                       f"\n\nLast error:\n{last_error}",
                details={
                    "commands_tried": commands_tried,
                    "last_error": last_error
                }
            )
            
        except Exception as e:
            logger.error(f"Critical error running {test_type} tests: {e}")
            return TestResult(
                test_type=test_type,
                status="failed",
                output=f"Critical error: {str(e)}",
                details={"exception": str(e)}
            )
    
    def _get_test_commands(self, test_type: str) -> List[List[str]]:
        """
        Get commands for specific test type with fallback options.
        Returns multiple command options in order of preference.
        """
        commands_map = {
            # Laravel tests with fallbacks
            "pest": [
                ["php", "artisan", "test"],
                ["./vendor/bin/pest"],
                ["composer", "test"]
            ],
            "phpstan": [
                ["./vendor/bin/phpstan", "analyse"],
                ["vendor/bin/phpstan", "analyse"],
                ["composer", "phpstan"]
            ],
            "pint": [
                ["./vendor/bin/pint", "--test"],
                ["vendor/bin/pint", "--test"],
                ["composer", "pint"]
            ],
            
            # JavaScript/Node tests with fallbacks
            "jest": [
                ["npm", "test"],
                ["yarn", "test"],
                ["npx", "jest"]
            ],
            "eslint": [
                ["npm", "run", "lint"],
                ["yarn", "lint"],
                ["npx", "eslint", "."]
            ],
            
            # Vue.js tests with multiple options
            "vue": [
                ["npm", "run", "test:unit"],
                ["yarn", "test:unit"], 
                ["npx", "vitest", "run"],
                ["npm", "test"]
            ],
            
            # Python tests with fallbacks
            "python": [
                ["pytest"],
                ["python", "-m", "pytest"],
                ["python3", "-m", "pytest"]
            ],
            
            # Other test types
            "playwright": [["npx", "playwright", "test"]],
            "composer": [["composer", "test"]],
            "npm": [["npm", "test"]],
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
    
    async def validate_patch(self, project_path: Optional[str], patch_text: str, stack: str) -> bool:
        """
        Validate if a patch can be applied and meets basic quality checks.
        Used by DeveloperAgent to validate patches before applying.
        """
        try:
            logger.info(f"Validating patch for stack '{stack}' in project: {project_path}")
            
            # 1. Basic format validation
            if not is_valid_patch(patch_text):
                logger.warning("Patch validation failed: Invalid patch format")
                return False
            
            # 2. Check if project path exists
            if not project_path or not os.path.exists(project_path):
                logger.warning(f"Patch validation failed: Project path does not exist: {project_path}")
                return False
            
            # 3. Try to apply patch with --check (dry run)
            normalized_patch = self._normalize_patch(patch_text, project_path)
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.patch', delete=False, encoding='utf-8') as f:
                f.write(normalized_patch)
                patch_file = f.name
            
            try:
                check_result = await self._run_command(
                    ["git", "apply", "--check", patch_file],
                    cwd=project_path
                )
                
                if check_result.returncode == 0:
                    logger.info("✅ Patch validation successful - can be applied cleanly")
                    return True
                else:
                    logger.warning(f"❌ Patch validation failed - git check failed: {check_result.stderr}")
                    return False
                    
            finally:
                try:
                    os.unlink(patch_file)
                except:
                    pass
            
        except Exception as e:
            logger.error(f"Error validating patch: {e}")
            return False
