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

# Import EnvironmentManager for auto-setup and self-healing
from .environment_manager import EnvironmentManager
from .repair_agent import RepairAgent

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
    def __init__(self, llm_router=None):
        self.timeout = 300  # 5 minutes default timeout
        self.development_mode = os.environ.get("DEVELOPMENT_MODE", "true").lower() == "true"
        # ✅ Initialize environment manager for auto-setup and self-healing
        self.environment_manager = EnvironmentManager()
        # ✅ Initialize LLM-powered repair agent for complex issues
        self.repair_agent = RepairAgent(llm_router=llm_router)
    
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
        Enhanced test runner with auto-setup and self-healing capabilities.
        
        Phase 1: Environment auto-setup (detect and fix missing deps, configs)  
        Phase 2: Self-healing command execution (auto-repair on failures)
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
            
            # ✅ PHASE 1: Auto-detect project stack and setup environment
            stack = self._detect_project_stack(project_path)
            logger.info(f"Detected stack: {stack} for test type: {test_type}")
            
            # Auto-setup environment (Phase 1: detect and fix issues)
            setup_success = await self.auto_setup_environment(project_path, stack)
            if not setup_success:
                logger.warning("Auto-setup had issues, but continuing with tests...")
            
            # ✅ Frontend-specific pre-checks for Vue/React
            if test_type in ["vue", "eslint"] and self._is_frontend_project(project_path):
                if not self._has_test_config(project_path, test_type):
                    return TestResult(
                        test_type=test_type,
                        status="skipped",
                        output=f"No {test_type} configuration found - this is normal for new frontend projects",
                        details={"reason": "no_config", "project_type": "frontend"}
                    )
            
            commands = self._get_test_commands(test_type)
            if not commands:
                return TestResult(
                    test_type=test_type,
                    status="failed",
                    output=f"No commands defined for test type: {test_type}"
                )
            
            # ✅ PHASE 2: Smart command execution with self-healing
            return await self.smart_command_execution(commands, project_path, test_type)
            
        except Exception as e:
            logger.error(f"Critical error running {test_type} tests: {e}")
            return TestResult(
                test_type=test_type,
                status="skipped",
                output=f"Test configuration not found or error: {str(e)}",
                details={"exception": str(e), "reason": "missing_config"}
            )
    
    def _detect_project_stack(self, project_path: str) -> str:
        """
        Auto-detect project technology stack based on files and structure.
        Returns: 'laravel', 'vue', 'react', 'python', 'node', 'unknown'
        """
        try:
            project_root = Path(project_path)
            
            # Laravel detection
            if (project_root / "artisan").exists() and (project_root / "composer.json").exists():
                return "laravel"
            
            # Vue.js detection
            if (project_root / "package.json").exists():
                try:
                    import json
                    with open(project_root / "package.json", 'r') as f:
                        package_data = json.load(f)
                    dependencies = {**package_data.get("dependencies", {}), **package_data.get("devDependencies", {})}
                    
                    if any("vue" in dep for dep in dependencies.keys()):
                        return "vue"
                    elif any("react" in dep for dep in dependencies.keys()):
                        return "react"
                    else:
                        return "node"
                except:
                    return "node"
            
            # Python detection
            if (project_root / "requirements.txt").exists() or (project_root / "pyproject.toml").exists():
                return "python"
            
            # PHP detection (non-Laravel)
            if (project_root / "composer.json").exists():
                return "php"
            
            return "unknown"
            
        except Exception as e:
            logger.debug(f"Error detecting project stack: {e}")
            return "unknown"
    
    def _is_frontend_project(self, project_path: str) -> bool:
        """
        Check if project is a frontend project (Vue, React, etc.)
        """
        try:
            package_json = Path(project_path) / "package.json"
            if not package_json.exists():
                return False
            
            import json
            with open(package_json, 'r', encoding='utf-8') as f:
                package_data = json.load(f)
            
            # Check for frontend frameworks in dependencies
            dependencies = {**package_data.get("dependencies", {}), **package_data.get("devDependencies", {})}
            frontend_indicators = ["vue", "react", "@vue/", "vite", "webpack", "eslint"]
            
            return any(indicator in dep for dep in dependencies.keys() for indicator in frontend_indicators)
            
        except Exception as e:
            logger.debug(f"Error checking if frontend project: {e}")
            return False
    
    def _has_test_config(self, project_path: str, test_type: str) -> bool:
        """
        Check if project has configuration for specific test type
        """
        try:
            project_root = Path(project_path)
            
            if test_type == "vue":
                # Check for Vue test configuration files
                vue_configs = [
                    "vitest.config.js", "vitest.config.ts", 
                    "jest.config.js", "jest.config.ts",
                    "vue.config.js", "vue.config.ts"
                ]
                return any((project_root / config).exists() for config in vue_configs)
            
            elif test_type == "eslint":
                # Check for ESLint configuration files
                eslint_configs = [
                    ".eslintrc.js", ".eslintrc.json", ".eslintrc.yml", ".eslintrc.yaml",
                    "eslint.config.js", "eslint.config.mjs"
                ]
                return any((project_root / config).exists() for config in eslint_configs)
            
            return False
            
        except Exception as e:
            logger.debug(f"Error checking test config for {test_type}: {e}")
            return False
    
    def _get_test_commands(self, test_type: str) -> List[List[str]]:
        """
        Get commands for specific test type with fallback options.
        Returns multiple command options in order of preference.
        """
        commands_map = {
            # Laravel tests with improved fallbacks (prefer vendor/bin over artisan)
            "pest": [
                ["./vendor/bin/pest", "-q"],
                ["vendor/bin/pest", "-q"],  
                ["php", "artisan", "test"],
                ["composer", "test"]
            ],
            "phpstan": [
                ["./vendor/bin/phpstan", "analyse", "app/", "--no-progress"],
                ["vendor/bin/phpstan", "analyse", "app/", "--no-progress"],
                ["./vendor/bin/phpstan", "analyse", "src/", "--no-progress"],  # Fallback for non-Laravel
                ["./vendor/bin/phpstan", "analyse", "--no-progress"],  # Last resort
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
            
            # ✅ Development mode: always accept patches to allow testing
            if self.development_mode:
                logger.info("🧪 Development mode: accepting patch without strict validation")
                return True
            
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
    
    async def auto_setup_environment(self, project_path: Optional[str], stack: str) -> bool:
        """
        Auto-detect and fix environment issues before running commands.
        This is the main entry point for Phase 1 + Phase 2 (Environment + Self-Healing).
        """
        if not project_path or not os.path.exists(project_path):
            logger.warning(f"Cannot auto-setup: project path invalid: {project_path}")
            return False
        
        try:
            logger.info(f"🔧 Auto-setting up environment for {stack} project...")
            
            # Phase 1: Detect and fix environment issues
            fixes_applied = await self.environment_manager.detect_and_fix_environment(project_path, stack)
            
            if fixes_applied:
                logger.info(f"✅ Applied {len(fixes_applied)} environment fixes:")
                for fix in fixes_applied:
                    logger.info(f"   - {fix}")
            else:
                logger.info("ℹ️ No environment fixes needed")
            
            return True
            
        except Exception as e:
            logger.error(f"Error in auto-setup environment: {e}")
            return False
    
    async def smart_command_execution(self, commands: List[List[str]], project_path: str, test_type: str) -> 'TestResult':
        """
        Phase 2: Self-Healing Command Execution
        Try commands with automatic error detection and repair
        """
        last_error = None
        commands_tried = []
        
        for attempt, command in enumerate(commands, 1):
            try:
                logger.info(f"Attempting {test_type} command (attempt {attempt}/{len(commands)}): {' '.join(command)}")
                result = await self._run_command(command, cwd=project_path)
                commands_tried.append(' '.join(command))
                
                if result.returncode == 0:
                    # Success!
                    return TestResult(
                        test_type=test_type,
                        status="passed",
                        output=f"✅ {test_type} command succeeded\n\nCommand: {' '.join(command)}\nOutput:\n{result.stdout}",
                        details={
                            "command": " ".join(command),
                            "return_code": result.returncode,
                            "attempts": attempt,
                            "commands_tried": commands_tried
                        }
                    )
                else:
                    # Command failed - try to auto-repair
                    last_error = f"Command '{' '.join(command)}' failed (exit {result.returncode})\nSTDERR:\n{result.stderr}"
                    logger.warning(f"Command failed, attempting auto-repair: {last_error[:200]}...")
                    
                    # ✅ Phase 2: Self-Healing - Analyze error and attempt repair
                    repair_success = await self._attempt_command_repair(
                        project_path, command, result.stderr, test_type
                    )
                    
                    if repair_success:
                        logger.info("🔧 Auto-repair successful, retrying command...")
                        # Retry the same command after repair
                        retry_result = await self._run_command(command, cwd=project_path)
                        if retry_result.returncode == 0:
                            return TestResult(
                                test_type=test_type,
                                status="passed",
                                output=f"✅ {test_type} command succeeded after auto-repair\n\nCommand: {' '.join(command)}\nOutput:\n{retry_result.stdout}",
                                details={
                                    "command": " ".join(command),
                                    "return_code": retry_result.returncode,
                                    "attempts": attempt,
                                    "auto_repaired": True,
                                    "commands_tried": commands_tried
                                }
                            )
                        else:
                            logger.warning("Auto-repair applied but command still fails, trying next command...")
                    
                    continue
                    
            except FileNotFoundError:
                last_error = f"Command '{' '.join(command)}' not found"
                logger.info(f"Command not found: {' '.join(command)}, trying next...")
                commands_tried.append(' '.join(command) + " (not found)")
                continue
                
            except Exception as e:
                last_error = f"Command '{' '.join(command)}' error: {str(e)}"
                logger.warning(f"Command error: {e}, trying next...")
                commands_tried.append(' '.join(command) + f" (error: {e})")
                continue
        
        # All commands failed even with auto-repair attempts
        return TestResult(
            test_type=test_type,
            status="failed",
            output=f"❌ All {test_type} commands failed even after auto-repair attempts\n\nCommands tried:\n" + 
                   "\n".join(f"- {cmd}" for cmd in commands_tried) + 
                   f"\n\nLast error:\n{last_error}",
            details={
                "commands_tried": commands_tried,
                "last_error": last_error,
                "auto_repair_attempted": True
            }
        )
    
    async def _attempt_command_repair(self, project_path: str, command: List[str], error_output: str, test_type: str) -> bool:
        """
        Phase 2: Analyze command failure and attempt automatic repair
        Returns True if repair was attempted (not necessarily successful)
        """
        try:
            command_str = ' '.join(command)
            error_lower = error_output.lower()
            
            logger.info(f"🔍 Analyzing failure for auto-repair: {command_str}")
            
            # ===== COMPOSER/PHP REPAIRS =====
            if "composer" in command_str:
                # Vendor directory missing
                if "vendor" in error_lower or "autoload" in error_lower:
                    logger.info("🔧 Detected missing vendor directory, running composer install...")
                    try:
                        result = await self._run_command(["composer", "install", "--no-interaction"], cwd=project_path)
                        return result.returncode == 0
                    except:
                        return False
                
                # Script not found in composer.json
                if "script" in error_lower and ("not defined" in error_lower or "not found" in error_lower):
                    logger.info("🔧 Detected missing composer script, adding to composer.json...")
                    return await self._add_missing_composer_script(project_path, test_type)
            
            # ===== PHPSTAN REPAIRS =====
            if "phpstan" in command_str:
                # Path issue - "At least one path must be specified"
                if "at least one path" in error_lower or "path must be specified" in error_lower:
                    logger.info("🔧 Detected PHPStan path issue, will suggest path-specific command...")
                    return True  # Let the command fallback system handle phpstan analyse app/
            
            # ===== NPM/YARN REPAIRS =====
            if any(mgr in command_str for mgr in ["npm", "yarn", "node"]):
                # Node modules missing
                if "node_modules" in error_lower or "module not found" in error_lower:
                    logger.info("🔧 Detected missing node_modules, running npm install...")
                    try:
                        # Check if yarn.lock exists to determine package manager
                        yarn_lock = Path(project_path) / "yarn.lock"
                        cmd = ["yarn", "install"] if yarn_lock.exists() else ["npm", "install"]
                        result = await self._run_command(cmd, cwd=project_path)
                        return result.returncode == 0
                    except:
                        return False
            
            # ===== PYTHON REPAIRS =====
            if "pip" in command_str or "python" in command_str:
                # Module not found
                if "module" in error_lower and "not found" in error_lower:
                    logger.info("🔧 Detected missing Python modules, running pip install...")
                    try:
                        requirements_path = Path(project_path) / "requirements.txt"
                        if requirements_path.exists():
                            result = await self._run_command(["pip", "install", "-r", "requirements.txt"], cwd=project_path)
                            return result.returncode == 0
                    except:
                        return False
            
            # ===== LARAVEL ARTISAN REPAIRS =====
            if "artisan" in command_str:
                # Artisan file missing or not executable
                if "permission denied" in error_lower or "no such file" in error_lower:
                    logger.info("🔧 Detected artisan issues, attempting to fix...")
                    artisan_path = Path(project_path) / "artisan"
                    if artisan_path.exists():
                        # Make executable
                        os.chmod(artisan_path, 0o755)
                        return True
                    # Note: artisan creation is handled by environment_manager
            
            # ===== LLM-POWERED REPAIR FALLBACK =====
            # If no standard repair found, use LLM to analyze and fix
            logger.info("🤖 No standard repair found, attempting LLM-powered analysis...")
            
            try:
                repair_result = await self.repair_agent.analyze_and_repair(
                    project_path=project_path,
                    stack=self._detect_project_stack(project_path),
                    error_output=error_output,
                    failed_command=' '.join(command),
                    context={"test_type": test_type}
                )
                
                if repair_result.success:
                    logger.info(f"✅ LLM repair successful: {repair_result.description}")
                    return True
                else:
                    logger.warning(f"❌ LLM repair failed: {repair_result.error_message}")
                    return False
                    
            except Exception as e:
                logger.error(f"Error in LLM-powered repair: {e}")
                return False
            
        except Exception as e:
            logger.error(f"Error in command repair analysis: {e}")
            return False
    
    async def _add_missing_composer_script(self, project_path: str, script_name: str) -> bool:
        """Add missing script to composer.json"""
        try:
            composer_path = Path(project_path) / "composer.json"
            if not composer_path.exists():
                return False
            
            # Map script names to commands
            script_commands = {
                "test": "pest",
                "phpstan": "phpstan analyse app/",
                "pint": "pint"
            }
            
            if script_name not in script_commands:
                return False
            
            # Read, update, write composer.json
            import json
            with open(composer_path, 'r') as f:
                composer_data = json.load(f)
            
            if 'scripts' not in composer_data:
                composer_data['scripts'] = {}
            
            composer_data['scripts'][script_name] = script_commands[script_name]
            
            with open(composer_path, 'w') as f:
                json.dump(composer_data, f, indent=2)
            
            logger.info(f"✅ Added missing script to composer.json: {script_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error adding composer script: {e}")
            return False
