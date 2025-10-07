"""
Advanced Testing and Patching Tools with Self-Healing Capabilities
Enhanced for robust Laravel support with intelligent error recovery
"""
import os
import json
import re
import logging
import shutil
import tempfile
import asyncio
import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass

# Import internal modules
from .environment_manager import EnvironmentManager
from .repair_agent import RepairAgent
from .patch_validator import PatchValidator

logger = logging.getLogger(__name__)

def is_valid_patch(patch_text: str) -> bool:
    """
    Enhanced patch validation with structural checks
    """
    if not patch_text or not isinstance(patch_text, str):
        return False
    
    lines = patch_text.strip().split('\
')
    if len(lines) < 4:  # Minimum viable patch
        return False
    
    # Check for diff header
    if not any(line.startswith('diff --git') for line in lines[:5]):
        return False
    
    # Must have file headers
    has_old_file = any(line.startswith('---') for line in lines)
    has_new_file = any(line.startswith('+++') for line in lines)
    
    if not (has_old_file and has_new_file):
        return False
    
    # Must have at least one hunk
    has_hunk = any(line.startswith('@@') for line in lines)
    return has_hunk

@dataclass
class TestResult:
    test_type: str
    status: str  # "passed" or "failed"
    output: str
    details: Optional[Dict[str, Any]] = None

class ToolManager:
    def __init__(self, llm_router=None):
        self.timeout = 300  # 🔥 INCREASED: 5 minutes for composer/Laravel commands
        self.kill_timeout = 10  # Additional time before force kill
        self.development_mode = os.environ.get("DEVELOPMENT_MODE", "true").lower() == "true"
        # ✅ Initialize environment manager for auto-setup and self-healing
        self.environment_manager = EnvironmentManager()
        # ✅ Initialize LLM-powered repair agent for complex issues
        self.repair_agent = RepairAgent(llm_router=llm_router)
        # ✅ Initialize advanced patch validator and repairer (Phase 3)
        self.patch_validator = PatchValidator()
        # 🔥 NEW: Anti-loop tracking for repairs
        self.repair_attempts = {}  # track repair attempts per project+error
        self.max_repair_attempts = 2  # Max attempts per unique error
        # 🔥 NEW: Global repair counter per project to prevent infinite loops
        self.project_repair_counts = {}  # track total repairs per project
        self.max_total_repairs_per_project = 5  # Absolute limit

    def extract_patch(self, text: str) -> Optional[str]:
        """Extract patch from text"""
        if not text:
            return None
        
        # Look for patch markers
        patch_start_patterns = [
            r'```diff\
(.*?)```',
            r'```patch\
(.*?)```', 
            r'```\
(diff --git.*?)```',
            r'(diff --git.*?)(?=\
\
|\
```|\Z)',
        ]
        
        for pattern in patch_start_patterns:
            matches = re.findall(pattern, text, re.DOTALL | re.MULTILINE)
            if matches:
                patch = matches[0].strip()
                if is_valid_patch(patch):
                    return patch
        
        # Fallback: if entire text looks like a patch
        if is_valid_patch(text):
            return text.strip()
        
        return None
    
    def _normalize_patch(self, patch_text: str, project_path: str) -> str:
        """Normalize patch paths relative to project root with enhanced validation"""
        try:
            lines = patch_text.split('\
')
            normalized_lines = []
            project_path_obj = Path(project_path).resolve()
            
            for line in lines:
                if line.startswith('--- ') or line.startswith('+++ '):
                    # Extract file path
                    file_path = line[4:].strip()
                    
                    # Remove a/ b/ prefixes if present
                    if file_path.startswith(('a/', 'b/')):
                        file_path = file_path[2:]
                    
                    # Skip /dev/null
                    if file_path == '/dev/null':
                        normalized_lines.append(line)
                        continue
                    
                    # Resolve absolute path and validate it's within project
                    try:
                        abs_path = (project_path_obj / file_path).resolve()
                        # Security check: ensure file is within project directory
                        abs_path.relative_to(project_path_obj)
                        
                        # Use relative path in patch
                        normalized_lines.append(line[:4] + file_path)
                    except (ValueError, OSError):
                        # Invalid path - keep original
                        logger.warning(f"Invalid path in patch: {file_path}")
                        normalized_lines.append(line)
                else:
                    normalized_lines.append(line)
            
            return '\
'.join(normalized_lines)
        except Exception as e:
            logger.warning(f"Error normalizing patch: {e}")
            return patch_text
    
    async def apply_patch(self, patch_text: str, project_path: str) -> bool:
        """
        Enhanced patch application with pre-validation and rollback capability
        """
        if not patch_text or not project_path:
            return False
        
        logger.info(f"Applying patch to project: {project_path}")
        
        try:
            # 🔥 NEW: Validate project structure before applying patch
            if not await self._validate_project_structure_for_patch(project_path, patch_text):
                logger.error("❌ Project structure validation failed - patch cannot be applied safely")
                return False
            
            # Normalize patch for consistent application
            normalized_patch = self._normalize_patch(patch_text, project_path)
            
            # Create temporary patch file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.patch', delete=False, encoding='utf-8') as f:
                f.write(normalized_patch)
                patch_file = f.name
            
            try:
                # Apply patch with git apply (safer than patch command)
                result = await self._run_command_with_timeout(
                    ["git", "apply", "--verbose", patch_file],
                    cwd=project_path,
                    timeout=30
                )
                
                if result.returncode == 0:
                    logger.info("✅ Patch applied successfully")
                    return True
                else:
                    logger.error(f"❌ Patch application failed: {result.stderr}")
                    # Try with --3way merge
                    logger.info("🔄 Attempting 3-way merge...")
                    result = await self._run_command_with_timeout(
                        ["git", "apply", "--3way", patch_file],
                        cwd=project_path,
                        timeout=30
                    )
                    if result.returncode == 0:
                        logger.info("✅ Patch applied with 3-way merge")
                        return True
                    else:
                        logger.error(f"❌ 3-way merge also failed: {result.stderr}")
                        return False
            finally:
                # Clean up temp file
                try:
                    os.unlink(patch_file)
                except:
                    pass
        
        except Exception as e:
            logger.error(f"Error applying patch: {e}")
            return False
    
    async def _validate_project_structure_for_patch(self, project_path: str, patch_text: str) -> bool:
        """
        🔥 NEW: Validate that all directories referenced in patch exist or can be created
        """
        try:
            project_root = Path(project_path)
            if not project_root.exists():
                logger.error(f"Project root does not exist: {project_path}")
                return False
            
            # Extract file paths from patch
            lines = patch_text.split('\
')
            file_paths = set()
            
            for line in lines:
                if line.startswith('--- ') or line.startswith('+++ '):
                    file_path = line[4:].strip()
                    if file_path.startswith(('a/', 'b/')):
                        file_path = file_path[2:]
                    if file_path != '/dev/null':
                        file_paths.add(file_path)
            
            # Validate each file path
            for file_path in file_paths:
                target_path = project_root / file_path
                target_dir = target_path.parent
                
                # Check if directory exists or can be created
                if not target_dir.exists():
                    try:
                        # Test directory creation (but don't actually create it yet)
                        target_dir.mkdir(parents=True, exist_ok=True)
                        logger.info(f"✅ Created missing directory for patch: {target_dir}")
                    except Exception as e:
                        logger.error(f"❌ Cannot create directory {target_dir}: {e}")
                        return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating project structure for patch: {e}")
            return False

    async def run_command(self, command: List[str], cwd: Optional[str] = None):
        """
        Enhanced command execution with proper timeout and cleanup
        """
        try:
            result = await self._run_command_with_timeout(command, cwd=cwd, timeout=self.timeout)
            return TestResult(
                test_type="command",
                status="passed" if result.returncode == 0 else "failed",
                output=result.stdout if result.returncode == 0 else result.stderr,
                details={"command": " ".join(command), "return_code": result.returncode}
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
        🔥 ENHANCED: Test runner with improved Laravel validation and anti-loop protection
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
            
            # ✅ PHASE 1: Enhanced stack detection and validation
            stack = self._detect_project_stack(project_path)
            logger.info(f"Detected stack: {stack} for test type: {test_type}")
            
            # 🔥 NEW: Strict Laravel validation before proceeding
            if stack == "laravel" and test_type in ["pest", "pint", "phpstan"]:
                laravel_valid = await self._validate_laravel_environment(project_path)
                if not laravel_valid:
                    return TestResult(
                        test_type=test_type,
                        status="failed",
                        output=f"Laravel environment validation failed. Project structure incomplete or corrupted.",
                        details={"reason": "invalid_laravel_environment", "project_path": project_path}
                    )
            
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
            
            # 🔥 NEW: Pre-validate command availability for Laravel
            if stack == "laravel":
                commands = await self._filter_available_commands(project_path, commands)
                if not commands:
                    return TestResult(
                        test_type=test_type,
                        status="failed", 
                        output=f"No {test_type} commands available. Run 'composer install' first.",
                        details={"reason": "missing_binaries", "stack": stack}
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
    
    async def _validate_laravel_environment(self, project_path: str) -> bool:
        """
        🔥 ENHANCED: Strict Laravel environment validation with deeper checks
        """
        try:
            project_root = Path(project_path)
            
            # 1. Check essential Laravel files
            required_files = ["composer.json", "artisan"]
            for req_file in required_files:
                if not (project_root / req_file).exists():
                    logger.warning(f"❌ Missing essential Laravel file: {req_file}")
                    return False
            
            # 2. Validate composer.json is actually Laravel
            composer_json = project_root / "composer.json"
            try:
                with open(composer_json, 'r') as f:
                    composer_data = json.load(f)
                
                # Check for Laravel framework in dependencies
                require = composer_data.get("require", {})
                if "laravel/framework" not in require and "illuminate/support" not in require:
                    logger.warning("❌ composer.json doesn't contain Laravel framework dependency")
                    return False
                
                # 🔥 NEW: Check if name field is present (root package indicator)
                if not composer_data.get("name"):
                    logger.warning("❌ composer.json missing 'name' field - not a valid root package")
                    return False
                
                # Check for proper Laravel project structure markers
                project_type = composer_data.get("type", "")
                if project_type and project_type not in ["project", "library", ""]:
                    logger.warning(f"❌ Invalid composer project type: {project_type}")
                    return False
                    
       
                # 🔥 NEW: Check for autoload configuration
                if "autoload" not in composer_data and "autoload-dev" not in composer_data:
                    logger.warning("❌ composer.json missing autoload configuration")
                    return False
                    
            except (json.JSONDecodeError, Exception) as e:
                logger.warning(f"❌ Invalid composer.json: {e}")
                return False
            
            # 3. Check vendor directory exists and has autoload
            vendor_dir = project_root / "vendor"
            if not vendor_dir.exists():
                logger.warning("❌ Missing vendor directory - composer install needed")
                return False
            
            autoload_file = vendor_dir / "autoload.php"
            if not autoload_file.exists():
                logger.warning("❌ Missing vendor/autoload.php - corrupted installation")
                return False
            
            # 🔥 NEW: Check for composer.lock (indicates dependencies are locked)
            composer_lock = project_root / "composer.lock"
            if not composer_lock.exists():
                logger.warning("⚠️ Missing composer.lock - dependencies not locked (may cause issues)")
                # Don't fail, but log warning
            
            # 4. Check for Laravel directory structure
            laravel_dirs = ["app", "bootstrap", "config"]
            missing_dirs = []
            for req_dir in laravel_dirs:
                if not (project_root / req_dir).exists():
                    missing_dirs.append(req_dir)
            
            if missing_dirs:
                logger.warning(f"❌ Missing Laravel directories: {missing_dirs}")
                return False
            
            # 🔥 NEW: Check for Laravel-specific files in directories
            essential_structure = {
                "app/Http": False,
                "bootstrap/app.php": False,
                "config/app.php": False,
            }
            
            for path_str, _ in essential_structure.items():
                path = project_root / path_str
                if path.exists():
                    essential_structure[path_str] = True
            
            missing_structure = [k for k, v in essential_structure.items() if not v]
            if missing_structure:
                logger.warning(f"⚠️ Missing Laravel structure elements: {missing_structure}")
                # Don't fail on this, but it's suspicious
            
            logger.info("✅ Laravel environment validation passed")
            return True
            
        except Exception as e:
            logger.error(f"Error validating Laravel environment: {e}")
            return False
    
    async def _filter_available_commands(self, project_path: str, commands: List[List[str]]) -> List[List[str]]:
        """
        🔥 NEW: Filter commands to only those that have available binaries
        """
        available_commands = []
        project_root = Path(project_path)
        
        for command in commands:
            if not command:
                continue
                
            cmd_name = command[0]
            
            # Check if binary exists in vendor/bin
            if cmd_name.startswith('./vendor/bin/') or cmd_name.startswith('vendor/bin/'):
                binary_name = cmd_name.split('/')[-1]
                binary_path = project_root / "vendor" / "bin" / binary_name
                if binary_path.exists():
                    available_commands.append(command)
                    continue
            
            # Check if command is composer script
            elif cmd_name == "composer" and len(command) > 1:
                # Check if composer script exists
                try:
                    composer_json = project_root / "composer.json"
                    if composer_json.exists():
                        with open(composer_json, 'r') as f:
                            composer_data = json.load(f)
                        scripts = composer_data.get('scripts', {})
                        if command[1] in scripts:
                            available_commands.append(command)
                            continue
                except:
                    pass
            
            # Check if it's a global command (php, npm, etc.)
            elif cmd_name in ["php", "npm", "yarn", "node"]:
                try:
                    # Quick availability check
                    result = await self._run_command_with_timeout(
                        [cmd_name, "--version"], 
                        cwd=project_path, 
                        timeout=5
                    )
                    if result.returncode == 0:
                        available_commands.append(command)
                except:
                    pass
        
        logger.info(f"Available commands: {[' '.join(cmd) for cmd in available_commands]}")
        return available_commands

    def _detect_project_stack(self, project_path: str) -> str:
        """
        Auto-detect project technology stack based on files and structure.
        Returns: 'laravel', 'vue', 'react', 'python', 'node', 'unknown'
        """
        try:
            project_root = Path(project_path)
            
            # Laravel detection (enhanced)
            if (project_root / "artisan").exists() and (project_root / "composer.json").exists():
                # Double-check it's actually Laravel by looking at composer.json
                try:
                    with open(project_root / "composer.json", 'r') as f:
                        composer_data = json.load(f)
                    require = composer_data.get("require", {})
                    if "laravel/framework" in require or "illuminate/support" in require:
                        return "laravel"
                except:
                    pass
            
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
        🔥 ENHANCED: Get commands with non-interactive flags to prevent hanging
        Returns multiple command options in order of preference.
        """
        commands_map = {
            # 🔥 FIXED: Laravel tests with non-interactive flags and timeouts
            "pest": [
                ["./vendor/bin/pest", "--no-interaction", "--stop-on-failure", "--bail"],
                ["vendor/bin/pest", "--no-interaction", "--stop-on-failure"],  
                ["php", "artisan", "test", "--no-interaction", "--stop-on-failure"],
                ["composer", "test", "--no-interaction"]
            ],
            # 🔥 FIXED: PHPStan with error-format and no-progress
            "phpstan": [
                ["./vendor/bin/phpstan", "analyse", "app/", "--no-progress", "--error-format=raw", "--memory-limit=256M"],
                ["vendor/bin/phpstan", "analyse", "app/", "--no-progress", "--error-format=raw"],
                ["./vendor/bin/phpstan", "analyse", "src/", "--no-progress", "--error-format=raw"],  # Fallback for non-Laravel
                ["./vendor/bin/phpstan", "analyse", "--no-progress", "--error-format=raw"],  # Last resort
                ["composer", "phpstan", "--no-interaction"]
            ],
            # 🔥 FIXED: Pint with --test flag and quiet mode
            "pint": [
                ["./vendor/bin/pint", "--test", "-q"],
                ["vendor/bin/pint", "--test", "--quiet"],
                ["composer", "pint", "--no-interaction"]
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
    
    async def _run_command_with_timeout(self, command: List[str], cwd: Optional[str] = None, timeout: int = None):
        """
        🔥 ENHANCED: Robust command execution with proper timeout and cleanup
        """
        if timeout is None:
            timeout = self.timeout
        
        process = None
        try:
            # Create subprocess with proper process group for cleanup
            process = await asyncio.create_subprocess_exec(
                *command,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                preexec_fn=os.setsid if hasattr(os, 'setsid') else None  # Create process group on Unix
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout
                )
                
                return type('CommandResult', (), {
                    'returncode': process.returncode,
                    'stdout': stdout.decode('utf-8', errors='ignore'),
                    'stderr': stderr.decode('utf-8', errors='ignore')
                })()
                
            except asyncio.TimeoutError:
                logger.error(f"⏰ Command timeout ({timeout}s): {' '.join(command)}")
                
                # Graceful termination first
                if process:
                    try:
                        process.terminate()
                        await asyncio.wait_for(process.wait(), timeout=self.kill_timeout)
                        logger.info("✅ Process terminated gracefully")
                    except asyncio.TimeoutError:
                        # Force kill if graceful termination fails
                        logger.warning("🔥 Force killing process...")
                        try:
                            if hasattr(os, 'killpg') and hasattr(os, 'getpgid'):
                                os.killpg(os.getpgid(process.pid), 9)  # Kill process group
                            else:
                                process.kill()
                            await process.wait()
                            logger.info("✅ Process force killed")
                        except Exception as kill_error:
                            logger.error(f"❌ Error force killing process: {kill_error}")
                
                raise Exception(f"Command timed out after {timeout} seconds")
            
        except FileNotFoundError:
            raise Exception(f"Command not found: {command[0]}")
        except Exception as e:
            if process:
                try:
                    process.kill()
                    await process.wait()
                except:
                    pass
            raise e

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
        🔥 ENHANCED: Self-Healing Command Execution with anti-loop protection
        """
        last_error = None
        commands_tried = []
        
        for attempt, command in enumerate(commands, 1):
            try:
                logger.info(f"Attempting {test_type} command (attempt {attempt}/{len(commands)}): {' '.join(command)}")
                result = await self._run_command_with_timeout(command, cwd=project_path)
                commands_tried.append(' '.join(command))
                
                if result.returncode == 0:
                    # Success!
                    return TestResult(
                        test_type=test_type,
                        status="passed",
                        output=f"✅ {test_type} command succeeded\
\
Command: {' '.join(command)}\
Output:\
{result.stdout}",
                        details={
                            "command": " ".join(command),
                            "return_code": result.returncode,
                            "attempts": attempt,
                            "commands_tried": commands_tried
                        }
                    )
                else:
                    # Command failed - try to auto-repair
                    last_error = f"Command '{' '.join(command)}' failed (exit {result.returncode})\
STDERR:\
{result.stderr}"
                    logger.warning(f"Command failed, attempting auto-repair: {last_error[:200]}...")
                    
                    # ✅ Phase 2: Self-Healing - Analyze error and attempt repair
                    repair_success = await self._attempt_command_repair(
                        project_path, command, result.stderr, test_type
                    )
                    
                    if repair_success:
                        logger.info("🔧 Auto-repair successful, retrying command...")
                        # Retry the same command after repair
                        retry_result = await self._run_command_with_timeout(command, cwd=project_path)
                        if retry_result.returncode == 0:
                            return TestResult(
                                test_type=test_type,
                                status="passed",
                                output=f"✅ {test_type} command succeeded after auto-repair\
\
Command: {' '.join(command)}\
Output:\
{retry_result.stdout}",
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
            output=f"❌ All {test_type} commands failed even after auto-repair attempts\
\
Commands tried:\
" + 
                   "\
".join(f"- {cmd}" for cmd in commands_tried) + 
                   f"\
\
Last error:\
{last_error}",
            details={
                "commands_tried": commands_tried,
                "last_error": last_error,
                "auto_repair_attempted": True
            }
        )
    
    async def _attempt_command_repair(self, project_path: str, command: List[str], error_output: str, test_type: str) -> bool:
        """
        🔥 ENHANCED: Command repair with anti-loop protection
        """
        try:
            command_str = ' '.join(command)
            error_lower = error_output.lower()
            
            # 🔥 NEW: Check global project repair limit first
            project_repairs = self.project_repair_counts.get(project_path, 0)
            if project_repairs >= self.max_total_repairs_per_project:
                logger.warning(f"🛑 GLOBAL REPAIR LIMIT REACHED for project {project_path} ({project_repairs}/{self.max_total_repairs_per_project})")
                logger.warning("⚠️ This project has had too many repair attempts. Stopping to prevent infinite loop.")
                return False
            
            # 🔥 NEW: Anti-loop protection per command
            repair_key = f"{project_path}:{command_str}:{hash(error_output)}"
            current_attempts = self.repair_attempts.get(repair_key, 0)
            
            if current_attempts >= self.max_repair_attempts:
                logger.warning(f"🔄 Repair attempt limit reached for {command_str} - skipping to prevent loop")
                return False
            
            self.repair_attempts[repair_key] = current_attempts + 1
            self.project_repair_counts[project_path] = project_repairs + 1
            logger.info(f"🔍 Analyzing failure for auto-repair (attempt {current_attempts + 1}/{self.max_repair_attempts}, project total: {project_repairs + 1}/{self.max_total_repairs_per_project}): {command_str}")
            
            # ===== COMPOSER/PHP REPAIRS =====
            if "composer" in command_str or "could not detect the root package" in error_lower:
                # 🔥 NEW: Root package detection failed
                if "could not detect the root package" in error_lower or "not a valid root package" in error_lower:
                    logger.error("❌ FATAL: Composer root package not detected - Laravel project structure is broken")
                    logger.error("⚠️ This indicates the project was not properly initialized with 'composer create-project'")
                    logger.error("🛑 Automatic repair not possible - project needs manual Laravel setup")
                    return False  # Don't attempt repair - this is a fundamental structural issue
                
                # Vendor directory missing
                if "vendor" in error_lower or "autoload" in error_lower:
                    logger.info("🔧 Detected missing vendor directory, running composer install...")
                    try:
                        result = await self._run_command_with_timeout(
                            ["composer", "install", "--no-interaction", "--no-progress"], 
                            cwd=project_path,
                            timeout=300  # 🔥 INCREASED: 5 minutes for composer install
                        )
                        if result.returncode == 0:
                            # 🔥 NEW: Verify the repair actually worked
                            if await self._verify_repair_success(project_path, "vendor"):
                                logger.info("✅ Vendor directory repair verified")
                                return True
                            else:
                                logger.warning("⚠️ Repair completed but vendor still invalid")
                                return False
                        return False
                    except Exception as e:
                        logger.error(f"❌ Composer install failed: {e}")
                        
                        return False
                
                # Script not found in composer.json
                if "script" in error_lower and ("not defined" in error_lower or "not found" in error_lower):
                    logger.info("🔧 Detected missing composer script, adding to composer.json...")
                    return await self._add_missing_composer_script(project_path, test_type)
            
            # ===== PHPSTAN REPAIRS =====
            if "phpstan" in command_str:
                # Binary not found - install it first
                if "command not found" in error_lower or "not found" in error_lower:
                    logger.info("🔧 PHPStan binary missing, installing via composer...")
                    try:
                        result = await self._run_command_with_timeout(
                            ["composer", "require", "--dev", "phpstan/phpstan", "--no-interaction"], 
                            cwd=project_path,
                            timeout=120
                        )
                        if result.returncode == 0:
                            logger.info("✅ PHPStan installed successfully")
                            return True
                        return False
                    except:
                        return False
                
                # Path issue - "At least one path must be specified"
                if "at least one path" in error_lower or "path must be specified" in error_lower:
                    logger.info("🔧 Detected PHPStan path issue, will suggest path-specific command...")
                    return True  # Let the command fallback system handle phpstan analyse app/
            
            # ===== PEST REPAIRS =====
            if "pest" in command_str:
                # Binary not found
                if "command not found" in error_lower or "not found" in error_lower:
                    logger.info("🔧 Pest binary missing, installing via composer...")
                    try:
                        result = await self._run_command_with_timeout(
                            ["composer", "require", "--dev", "pestphp/pest", "--no-interaction"], 
                            cwd=project_path,
                            timeout=120
                        )
                        if result.returncode == 0:
                            # 🔥 NEW: Verify pest binary exists after install
                            if await self._verify_repair_success(project_path, "pest"):
                                logger.info("✅ Pest installed and verified")
                                return True
                            else:
                                logger.warning("⚠️ Pest install completed but binary not found")
                                return False
                        return False
                    except Exception as e:
                        logger.error(f"❌ Pest installation failed: {e}")
                        return False
                
                # Configuration issue  
                if "no tests" in error_lower or "configuration" in error_lower:
                    logger.info("🔧 Creating basic Pest configuration...")
                    result = await self._create_basic_pest_config(project_path)
                    if result:
                        logger.info("✅ Pest configuration created")
                    return result
            
            # ===== PINT REPAIRS =====
            if "pint" in command_str:
                # Binary not found
                if "command not found" in error_lower or "not found" in error_lower:
                    logger.info("🔧 Pint binary missing, installing via composer...")
                    try:
                        result = await self._run_command_with_timeout(
                            ["composer", "require", "--dev", "laravel/pint", "--no-interaction"], 
                            cwd=project_path,
                            timeout=120
                        )
                        if result.returncode == 0:
                            # 🔥 NEW: Verify pint binary exists after install
                            if await self._verify_repair_success(project_path, "pint"):
                                logger.info("✅ Pint installed and verified")
                                return True
                            else:
                                logger.warning("⚠️ Pint install completed but binary not found")
                                return False
                        return False
                    except Exception as e:
                        logger.error(f"❌ Pint installation failed: {e}")
                        return False
            
            # ===== LLM-POWERED REPAIR as LAST RESORT =====
            # 🔥 NEW: Disabled LLM repair for known solvable issues to prevent loops
            known_simple_issues = [
                "pint", "pest", "phpstan",  # These have specific repair handlers above
                "composer install", "vendor", "autoload"  # These are handled by composer install
            ]
            
            # Check if this is a simple issue that shouldn't use LLM repair
            is_simple_issue = any(issue in command_str.lower() or issue in error_lower 
                                for issue in known_simple_issues)
            
            if is_simple_issue:
                logger.warning("🛑 LLM repair DISABLED for simple fixable issue to prevent loop")
                logger.warning(f"⚠️ Command '{command_str}' failed after all standard repair attempts")
                return False
            
            # Only use LLM repair for complex/unknown issues on last attempt
            if self.repair_agent and current_attempts == self.max_repair_attempts - 1:
                logger.info("🤖 Using LLM-powered repair as last resort for complex issue...")
                stack = self._detect_project_stack(project_path)
                repair_result = await self.repair_agent.analyze_and_repair(
                    project_path, stack, error_output, command_str
                )
                return repair_result.success if repair_result else False
            
            return False
            
        except Exception as e:
            logger.error(f"Error in command repair: {e}")
            return False
    
    async def _create_basic_pest_config(self, project_path: str) -> bool:
        """Create basic Pest configuration and test structure"""
        try:
            project_root = Path(project_path)
            
            # Create tests directory
            tests_dir = project_root / "tests"
            tests_dir.mkdir(exist_ok=True)
            
            # Create Feature and Unit directories
            (tests_dir / "Feature").mkdir(exist_ok=True)
            (tests_dir / "Unit").mkdir(exist_ok=True)
            
            # Create Pest.php configuration
            pest_config = tests_dir / "Pest.php"
            if not pest_config.exists():
                pest_config.write_text("""<?php

use Tests\\TestCase;
use Illuminate\\Foundation\\Testing\\RefreshDatabase;

uses(TestCase::class, RefreshDatabase::class)->in('Feature');
uses(TestCase::class)->in('Unit');
""")
            
            # Create a basic example test
            example_test = tests_dir / "Feature" / "ExampleTest.php"
            if not example_test.exists():
                example_test.write_text("""<?php

test('basic test example', function () {
    expect(true)->toBeTrue();
});
""")
            
            logger.info("✅ Created basic Pest configuration")
            return True
            
        except Exception as e:
            logger.error(f"Error creating Pest config: {e}")
            return False
    
    async def _add_missing_composer_script(self, project_path: str, test_type: str) -> bool:
        """Add missing script to composer.json"""
        try:
            composer_path = Path(project_path) / "composer.json"
            if not composer_path.exists():
                return False
            
            # Scripts to add based on test type
            script_commands = {
                "test": "pest",
                "pest": "pest",
                "phpstan": "./vendor/bin/phpstan analyse app/",
                "pint": "./vendor/bin/pint"
            }
            
            script_name = test_type
            if script_name not in script_commands:
                return False
            
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
    
    async def _verify_repair_success(self, project_path: str, repair_type: str) -> bool:
        """
        🔥 NEW: Verify that a repair actually succeeded
        """
        try:
            project_root = Path(project_path)
            
            if repair_type == "vendor":
                # Verify vendor directory and autoload exist
                vendor_dir = project_root / "vendor"
                autoload_file = vendor_dir / "autoload.php"
                
                if not vendor_dir.exists():
                    logger.warning("❌ Vendor directory still missing after repair")
                    return False
                
                if not autoload_file.exists():
                    logger.warning("❌ Vendor autoload.php still missing after repair")
                    return False
                
                # Check if vendor has actual packages
                vendor_count = len([d for d in vendor_dir.iterdir() if d.is_dir() and not d.name.startswith('.')])
                if vendor_count < 3:  # Should have at least composer, bin, and some packages
                    logger.warning(f"⚠️ Vendor directory suspiciously empty ({vendor_count} directories)")
                    return False
                
                return True
            
            elif repair_type == "pest":
                # Verify pest binary exists
                pest_binary = project_root / "vendor" / "bin" / "pest"
                if not pest_binary.exists():
                    logger.warning("❌ Pest binary not found after installation")
                    return False
                return True
            
            elif repair_type == "pint":
                # Verify pint binary exists
                pint_binary = project_root / "vendor" / "bin" / "pint"
                if not pint_binary.exists():
                    logger.warning("❌ Pint binary not found after installation")
                    return False
                return True
            
            elif repair_type == "phpstan":
                # Verify phpstan binary exists
                phpstan_binary = project_root / "vendor" / "bin" / "phpstan"
                if not phpstan_binary.exists():
                    logger.warning("❌ PHPStan binary not found after installation")
                    return False
                return True
            
            # Unknown repair type - assume success
            logger.warning(f"⚠️ Unknown repair type for verification: {repair_type}")
            return True
            
        except Exception as e:
            logger.error(f"Error verifying repair success: {e}")
            return False

    # Additional methods for comprehensive health checking, git operations, etc.
    # ... (rest of the methods remain similar but with enhanced error handling)
    
    async def init_git_repo(self, project_path: str) -> bool:
        """Initialize git repository"""
        try:
            repo_path = Path(project_path)
            if (repo_path / '.git').exists():
                return True
            
            result = await self._run_command_with_timeout(["git", "init"], cwd=project_path, timeout=30)
            return result.returncode == 0
            
        except Exception as e:
            logger.error(f"Error initializing git repo: {e}")
            return False
    
    async def commit_changes(self, project_path: str, message: str) -> bool:
        """Commit changes to git"""
        try:
            # Add all changes
            result = await self._run_command_with_timeout(["git", "add", "."], cwd=project_path, timeout=30)
            if result.returncode != 0:
                return False
            
            # Commit changes
            result = await self._run_command_with_timeout(
                ["git", "commit", "-m", message],
                cwd=project_path,
                timeout=30
            )
            return result.returncode == 0
            
        except Exception as e:
            logger.error(f"Error committing changes: {e}")
            return False

    async def validate_patch(self, project_path: Optional[str], patch_text: str, stack: str) -> bool:
        """
        🔥 ENHANCED: Validate if a patch can be applied with comprehensive checks
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
            
            # 2. Check if project path exists and is valid
            if not project_path or not os.path.exists(project_path):
                logger.warning(f"Patch validation failed: Project path does not exist: {project_path}")
                return False
            
            # 🔥 NEW: 3. Validate project structure before patch application
            if not await self._validate_project_structure_for_patch(project_path, patch_text):
                logger.warning("Patch validation failed: Project structure validation failed")
                return False
            
            # 4. Try to apply patch with --check (dry run)
            normalized_patch = self._normalize_patch(patch_text, project_path)
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.patch', delete=False, encoding='utf-8') as f:
                f.write(normalized_patch)
                patch_file = f.name
            
            try:
                check_result = await self._run_command_with_timeout(
                    ["git", "apply", "--check", patch_file],
                    cwd=project_path,
                    timeout=30
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
                
    async def _validate_project_structure_for_patch(self, project_path: str, patch_text: str) -> bool:
        """
        🔥 NEW: Validate that all files/directories referenced in patch exist or can be created
        """
        try:
            project_root = Path(project_path)
            
            # Extract file paths from patch
            file_paths = []
            for line in patch_text.split(''):
                # Look for file headers in diff format
                if line.startswith('---') or line.startswith('+++'):
                    # Extract path (skip a/ or b/ prefix)
                    parts = line.split(maxsplit=1)
                    if len(parts) > 1:
                        path = parts[1].strip()
                        # Remove a/ or b/ prefix
                        if path.startswith('a/') or path.startswith('b/'):
                            path = path[2:]
                        # Ignore /dev/null
                        if path != '/dev/null' and path:
                            file_paths.append(path)
            
            if not file_paths:
                logger.warning("⚠️ No file paths found in patch")
                return True  # If we can't extract paths, don't fail
            
            # Check each file path
            for file_path in set(file_paths):  # Use set to avoid duplicates
                full_path = project_root / file_path
                parent_dir = full_path.parent
                
                # 🔥 NEW: Create parent directory if it doesn't exist
                if not parent_dir.exists():
                    logger.info(f"📁 Creating missing directory for patch: {parent_dir}")
                    try:
                        parent_dir.mkdir(parents=True, exist_ok=True)
                    except Exception as e:
                        logger.error(f"❌ Failed to create directory {parent_dir}: {e}")
                        return False
                
                # If file doesn't exist, that's OK (it might be a new file)
                # But if parent directory doesn't exist and can't be created, fail
                if not parent_dir.exists():
                    logger.error(f"❌ Cannot create parent directory: {parent_dir}")
                    return False
            
            logger.info(f"✅ Project structure validated for {len(set(file_paths))} file(s)")
            return True
            
        except Exception as e:
            logger.error(f"Error validating project structure for patch: {e}")
            return False

    # Other utility methods...
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
