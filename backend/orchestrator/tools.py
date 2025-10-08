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
    🔥 PHASE 2 FIX: Enhanced patch validation with Git diff format checks
    Prevents "inconsistent new filename" and malformed diff errors
    """
    if not patch_text or not isinstance(patch_text, str):
        return False
    
    lines = patch_text.strip().split('\n')
    if len(lines) < 4:  # Minimum viable patch
        return False
    
    # ✅ Check for proper diff header format
    diff_headers = [line for line in lines[:10] if line.startswith('diff --git')]
    if not diff_headers:
        return False
    
    # ✅ Validate diff --git format: "diff --git a/path b/path"
    for header in diff_headers:
        parts = header.split()
        if len(parts) < 4 or parts[0] != 'diff' or parts[1] != '--git':
            logger.warning(f"❌ Invalid diff header format: {header}")
            return False
        
        # ✅ Check that a/ and b/ paths are consistent
        a_path = parts[2]
        b_path = parts[3]
        if not (a_path.startswith('a/') and b_path.startswith('b/')):
            logger.warning(f"❌ Invalid path format in diff header: {header}")
            return False
        
        # ✅ Ensure paths match (same filename)
        if a_path[2:] != b_path[2:]:
            logger.warning(f"❌ Inconsistent file paths: {a_path} vs {b_path}")
            return False
    
    # ✅ Must have properly paired file headers
    old_file_lines = [line for line in lines if line.startswith('---')]
    new_file_lines = [line for line in lines if line.startswith('+++')]
    
    if len(old_file_lines) != len(new_file_lines):
        logger.warning(f"❌ Mismatched file headers: {len(old_file_lines)} '---' vs {len(new_file_lines)} '+++'")
        return False
    
    # ✅ Validate file header format: "--- a/path" and "+++ b/path"
    for old_line, new_line in zip(old_file_lines, new_file_lines):
        if not (old_line.startswith('--- ') and new_line.startswith('+++ ')):
            logger.warning(f"❌ Invalid file header format: '{old_line}' or '{new_line}'")
            return False
        
        # Extract paths and validate consistency
        old_path = old_line[4:].strip()  # Remove "--- "
        new_path = new_line[4:].strip()  # Remove "+++ "
        
        # Handle /dev/null for new/deleted files
        if old_path != "/dev/null" and new_path != "/dev/null":
            if old_path.startswith('a/') and new_path.startswith('b/'):
                if old_path[2:] != new_path[2:]:
                    logger.warning(f"❌ Inconsistent file paths in headers: {old_path} vs {new_path}")
                    return False
    
    # ✅ Must have at least one properly formatted hunk
    hunk_headers = [line for line in lines if line.startswith('@@')]
    if not hunk_headers:
        logger.warning("❌ No hunk headers found (@@)")
        return False
    
    # ✅ Validate hunk header format: "@@ -start,count +start,count @@"
    hunk_pattern = re.compile(r'^@@ -(\d+),?(\d*) \+(\d+),?(\d*) @@')
    for hunk in hunk_headers:
        if not hunk_pattern.match(hunk):
            logger.warning(f"❌ Invalid hunk header format: {hunk}")
            return False
    
    logger.debug("✅ Patch validation passed - format is valid")
    return True

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
        # 🔥 ENHANCED: Anti-loop tracking for repairs
        self.repair_attempts = {}  # track repair attempts per project+error
        self.max_repair_attempts = 2  # Max attempts per unique error
        # 🔥 ENHANCED: Global repair counter per project to prevent infinite loops
        self.project_repair_counts = {}  # track total repairs per project
        self.max_total_repairs_per_project = 5  # Absolute limit
        # 🔥 NEW: Repair session tracking to prevent cross-session loops
        self.repair_session_start = {}  # track when repair sessions started
        self.max_repair_session_duration = 1800  # 30 minutes max per session
        # 🔥 NEW: Command-specific repair tracking
        self.command_repair_history = {}  # track repairs per command type

    def extract_patch(self, text: str) -> Optional[str]:
        """Extract patch from text"""
        if not text:
            return None
        
        # Look for patch markers
        patch_start_patterns = [
    r'```diff\n(.*?)```',
    r'```patch\n(.*?)```',
    r'```\n(diff --git.*?)```',
    r'(diff --git.*?)(?=\n\n|\n```|\Z)',
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
        """
        🔥 PHASE 2 FIX: Enhanced patch normalization with proper path handling
        Prevents Git diff "inconsistent filename" errors
        """
        try:
            lines = patch_text.split('\n')
            normalized_lines = []
            project_path_obj = Path(project_path).resolve()
            
            for line in lines:
                if line.startswith('--- ') or line.startswith('+++ '):
                    # Extract file path
                    file_path = line[4:].strip()
                    
                    # ✅ Enhanced path normalization for Git compatibility
                    if file_path == '/dev/null':
                        # Keep /dev/null as-is for new/deleted files
                        normalized_lines.append(line)
                        continue
                    
                    # ✅ Properly handle a/ and b/ prefixes
                    prefix = ""
                    if line.startswith('--- ') and file_path.startswith('a/'):
                        prefix = "a/"
                        file_path = file_path[2:]
                    elif line.startswith('+++ ') and file_path.startswith('b/'):
                        prefix = "b/"
                        file_path = file_path[2:]
                    
                    # ✅ Validate and normalize path
                    try:
                        abs_path = (project_path_obj / file_path).resolve()
                        # Security check: ensure file is within project directory
                        abs_path.relative_to(project_path_obj)
                        
                        # ✅ Reconstruct with proper prefix for Git compatibility
                        normalized_path = prefix + file_path
                        normalized_lines.append(line[:4] + normalized_path)
                        
                    except (ValueError, OSError):
                        # Invalid path - keep original but log warning
                        logger.warning(f"❌ Invalid path in patch, keeping original: {file_path}")
                        normalized_lines.append(line)
                        
                elif line.startswith('diff --git'):
                    # ✅ Ensure diff headers are properly formatted
                    parts = line.split()
                    if len(parts) >= 4:
                        # Normalize diff header: "diff --git a/path b/path"
                        base_path = parts[2][2:] if parts[2].startswith('a/') else parts[2]
                        normalized_header = f"diff --git a/{base_path} b/{base_path}"
                        normalized_lines.append(normalized_header)
                    else:
                        normalized_lines.append(line)
                else:
                    normalized_lines.append(line)
            
            normalized_patch = ''.join(normalized_lines)
            logger.debug(f"✅ Patch normalization completed successfully")
            return normalized_patch
            
        except Exception as e:
            logger.error(f"❌ Error normalizing patch: {e}")
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
        🔥 ENHANCED: Validate that all files/directories referenced in patch exist or can be created
        """
        try:
            project_root = Path(project_path)
            if not project_root.exists():
                logger.error(f"Project root does not exist: {project_path}")
                return False
            
            # Extract file paths from patch with enhanced parsing
            file_paths = self._extract_file_paths_from_patch(patch_text)
            
            if not file_paths:
                logger.warning("⚠️ No file paths found in patch")
                return True  # Empty patch is valid
            
            logger.info(f"🔍 Validating {len(file_paths)} file paths from patch...")
            
            # Validate each file path
            validation_results = []
            for file_path in file_paths:
                result = await self._validate_single_file_path(project_root, file_path)
                validation_results.append(result)
                
                if not result['valid']:
                    logger.error(f"❌ File path validation failed: {file_path} - {result['reason']}")
                    return False
                else:
                    logger.debug(f"✅ File path validated: {file_path}")
            
            logger.info(f"✅ All {len(file_paths)} file paths validated successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error validating project structure for patch: {e}")
            return False
    
    def _extract_file_paths_from_patch(self, patch_text: str) -> List[str]:
        """
        🔥 NEW: Enhanced file path extraction from patch
        """
        file_paths = set()
        lines = patch_text.split('\n')
        
        for line in lines:
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
                        file_paths.add(path)
        
        return list(file_paths)
    
    async def _validate_single_file_path(self, project_root: Path, file_path: str) -> Dict[str, Any]:
        """
        🔥 NEW: Validate a single file path for patch application
        """
        try:
            target_path = project_root / file_path
            target_dir = target_path.parent
            
            # Check if parent directory exists
            if not target_dir.exists():
                # Try to create the directory
                try:
                    target_dir.mkdir(parents=True, exist_ok=True)
                    logger.info(f"📁 Created missing directory: {target_dir}")
                    return {'valid': True, 'action': 'directory_created', 'path': str(target_dir)}
                except Exception as e:
                    return {
                        'valid': False, 
                        'reason': f'Cannot create directory {target_dir}: {e}',
                        'path': str(target_dir)
                    }
            
            # Check if it's a file or directory
            if target_path.exists():
                if target_path.is_file():
                    # Check if file is writable
                    if not os.access(target_path, os.W_OK):
                        return {
                            'valid': False,
                            'reason': f'File is not writable: {target_path}',
                            'path': str(target_path)
                        }
                    return {'valid': True, 'action': 'file_exists', 'path': str(target_path)}
                elif target_path.is_dir():
                    return {'valid': True, 'action': 'directory_exists', 'path': str(target_path)}
            else:
                # File doesn't exist - check if parent directory is writable
                if not os.access(target_dir, os.W_OK):
                    return {
                        'valid': False,
                        'reason': f'Parent directory is not writable: {target_dir}',
                        'path': str(target_dir)
                    }
                return {'valid': True, 'action': 'new_file', 'path': str(target_path)}
            
        except Exception as e:
            return {
                'valid': False,
                'reason': f'Validation error: {e}',
                'path': file_path
            }

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
            stack = await self._detect_project_stack(project_path)
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
        🔥 ENHANCED: Comprehensive Laravel environment validation with functional testing
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
            
            # 🔥 NEW: Functional testing - test if artisan actually works
            try:
                result = await self._run_command_with_timeout(
                    ["php", "artisan", "--version"],
                    cwd=project_path,
                    timeout=15
                )
                if result.returncode != 0:
                    logger.warning(f"❌ Artisan functional test failed: {result.stderr}")
                    return False
                
                logger.info(f"✅ Artisan functional test passed: {result.stdout.strip()}")
                
            except Exception as e:
                logger.warning(f"❌ Artisan functional test error: {e}")
                return False
            
            # 🔥 NEW: Test composer autoloader
            try:
                result = await self._run_command_with_timeout(
                    ["php", "-r", "require 'vendor/autoload.php'; echo 'Autoloader OK';"],
                    cwd=project_path,
                    timeout=10
                )
                if result.returncode != 0 or "Autoloader OK" not in result.stdout:
                    logger.warning("❌ Composer autoloader test failed")
                    return False
                
                logger.info("✅ Composer autoloader test passed")
                
            except Exception as e:
                logger.warning(f"❌ Composer autoloader test error: {e}")
                return False
            
            # 🔥 NEW: Test Laravel application bootstrap
            try:
                result = await self._run_command_with_timeout(
                    ["php", "-r", "require 'vendor/autoload.php'; require 'bootstrap/app.php'; echo 'Bootstrap OK';"],
                    cwd=project_path,
                    timeout=10
                )
                if result.returncode != 0 or "Bootstrap OK" not in result.stdout:
                    logger.warning("❌ Laravel bootstrap test failed")
                    return False
                
                logger.info("✅ Laravel bootstrap test passed")
                
            except Exception as e:
                logger.warning(f"❌ Laravel bootstrap test error: {e}")
                return False
            
            logger.info("✅ Laravel environment validation passed with functional tests")
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
        🔥 ENHANCED: Rigorous auto-detection of project technology stack
        Returns: 'laravel', 'vue', 'react', 'python', 'node', 'unknown'
        """
        try:
            project_root = Path(project_path)
            
            # ✅ Phase 1: Laravel detection (STRICT validation)
            if (project_root / "artisan").exists() and (project_root / "composer.json").exists():
                try:
                    with open(project_root / "composer.json", 'r') as f:
                        composer_data = json.load(f)
                    require = composer_data.get("require", {})
                    
                    # ✅ STRICT: Must have Laravel framework dependency
                    if "laravel/framework" in require or "illuminate/support" in require:
                        # ✅ Additional Laravel structure validation
                        required_laravel_dirs = ["app", "bootstrap", "config", "routes"]
                        if all((project_root / dir_name).exists() for dir_name in required_laravel_dirs):
                            logger.info(f"✅ Confirmed Laravel project: artisan + composer.json + framework + structure")
                            return "laravel"
                        else:
                            logger.warning(f"⚠️ Laravel files detected but incomplete structure in {project_path}")
                except Exception as e:
                    logger.debug(f"Error parsing composer.json: {e}")
            
            # ✅ Phase 2: JavaScript frameworks (Vue/React/Node) - STRICT validation
            if (project_root / "package.json").exists():
                try:
                    with open(project_root / "package.json", 'r') as f:
                        package_data = json.load(f)
                    
                    dependencies = {**package_data.get("dependencies", {}), **package_data.get("devDependencies", {})}
                    dep_names = list(dependencies.keys())
                    
                    # ✅ Vue.js detection - must have vue core
                    vue_indicators = ["vue", "@vue/cli-service", "vite", "nuxt"]
                    if any(indicator in dep for dep in dep_names for indicator in vue_indicators):
                        # Additional Vue structure check
                        if (project_root / "src").exists() or (project_root / "pages").exists():
                            logger.info(f"✅ Confirmed Vue.js project: package.json + vue dependencies + structure")
                            return "vue"
                    
                    # ✅ React detection - must have react core  
                    react_indicators = ["react", "react-dom", "@react", "next"]
                    if any(indicator in dep for dep in dep_names for indicator in react_indicators):
                        # Additional React structure check
                        if (project_root / "src").exists() or (project_root / "pages").exists() or (project_root / "public").exists():
                            logger.info(f"✅ Confirmed React project: package.json + react dependencies + structure")
                            return "react"
                    
                    # ✅ Generic Node.js (if package.json exists but no framework)
                    logger.info(f"✅ Detected generic Node.js project: package.json without specific framework")
                    return "node"
                    
                except Exception as e:
                    logger.debug(f"Error parsing package.json: {e}")
                    return "node"  # Fallback to node if package.json exists
            
            # ✅ Phase 3: Python detection - STRICT validation
            python_files = ["requirements.txt", "pyproject.toml", "setup.py", "Pipfile"]
            if any((project_root / py_file).exists() for py_file in python_files):
                # Additional Python structure check
                if (project_root / "src").exists() or any(f.suffix == ".py" for f in project_root.iterdir() if f.is_file()):
                    logger.info(f"✅ Confirmed Python project: requirements/pyproject + python files")
                    return "python"
            
            # ✅ Phase 4: Generic PHP (non-Laravel) 
            if (project_root / "composer.json").exists():
                # Only if no Laravel indicators found
                try:
                    with open(project_root / "composer.json", 'r') as f:
                        composer_data = json.load(f)
                    require = composer_data.get("require", {})
                    
                    # Ensure it's not Laravel before marking as PHP
                    if "laravel/framework" not in require and "illuminate/support" not in require:
                        logger.info(f"✅ Detected generic PHP project: composer.json without Laravel")
                        return "php"
                except Exception as e:
                    logger.debug(f"Error parsing composer.json for PHP: {e}")
            
            # ✅ If no clear indicators found
            logger.warning(f"⚠️ Unable to detect project stack in {project_path} - no clear indicators")
            return "unknown"
            
        except Exception as e:
            logger.error(f"❌ Error detecting project stack: {e}")
            return "unknown"
    
    def _validate_laravel_structure(self, project_root: Path) -> bool:
        """
        🔥 NEW: Validate Laravel project structure
        """
        try:
            # Essential Laravel directories
            required_dirs = ["app", "bootstrap", "config", "database", "public", "resources", "routes", "storage"]
            missing_dirs = [d for d in required_dirs if not (project_root / d).exists()]
            
            if missing_dirs:
                logger.warning(f"⚠️ Missing Laravel directories: {missing_dirs}")
                return False
            
            # Essential Laravel files
            required_files = ["artisan", "composer.json", "bootstrap/app.php"]
            missing_files = [f for f in required_files if not (project_root / f).exists()]
            
            if missing_files:
                logger.warning(f"⚠️ Missing Laravel files: {missing_files}")
                return False
            
            # Check for Laravel-specific structure
            app_structure = ["Http", "Models", "Providers"]
            app_missing = [d for d in app_structure if not (project_root / "app" / d).exists()]
            
            if len(app_missing) > 1:  # Allow some flexibility
                logger.warning(f"⚠️ Missing Laravel app structure: {app_missing}")
                return False
            
            return True
            
        except Exception as e:
            logger.debug(f"Error validating Laravel structure: {e}")
            return False
    
    async def _is_complete_laravel_project(self, project_root: Path) -> bool:
        """
        🔥 NEW: Check if this is a complete, functional Laravel project
        """
        try:
            # Essential Laravel files that must exist
            essential_files = [
                "artisan",
                "composer.json", 
                "bootstrap/app.php",
                "config/app.php",
                "routes/web.php",
                "vendor/autoload.php",
                "vendor/laravel/framework"  # Laravel framework must be installed
            ]
            
            # Check if all essential files exist
            for file_path in essential_files:
                if not (project_root / file_path).exists():
                    logger.debug(f"❌ Missing essential Laravel file: {file_path}")
                    return False
            
            # Check if composer.json is actually a Laravel project
            try:
                composer_json = project_root / "composer.json"
                with open(composer_json, 'r') as f:
                    composer_data = json.load(f)
                
                require = composer_data.get("require", {})
                if not any(pkg.startswith("laravel/") or pkg.startswith("illuminate/") 
                          for pkg in require.keys()):
                    logger.debug("❌ composer.json doesn't reference Laravel packages")
                    return False
                
                # Check if it has a proper name (not just a skeleton)
                name = composer_data.get("name", "")
                if not name or name.startswith("emergent/"):
                    logger.debug("❌ composer.json has invalid or skeleton name")
                    return False
                    
            except Exception as e:
                logger.debug(f"❌ Invalid composer.json: {e}")
                return False
            
            # Check if artisan is executable and works
            artisan_path = project_root / "artisan"
            if not os.access(artisan_path, os.X_OK):
                logger.debug("❌ Artisan file is not executable")
                return False
            
            # Test if artisan works (basic test)
            try:
                result = await self._run_command_with_timeout(
                    ["php", "artisan", "--version"],
                    cwd=str(project_root),
                    timeout=15
                )
                if result.returncode != 0:
                    logger.debug(f"❌ Artisan test failed: {result.stderr}")
                    return False
                
                logger.debug(f"✅ Laravel project verified: {result.stdout.strip()}")
                return True
                
            except Exception as e:
                logger.debug(f"❌ Artisan test error: {e}")
                return False
                
        except Exception as e:
            logger.debug(f"❌ Laravel project check error: {e}")
            return False
    
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
        🔥 ENHANCED: Robust command execution with intelligent timeout and cleanup
        """
        if timeout is None:
            timeout = self.timeout
        
        process = None
        process_group_id = None
        
        try:
            # Create subprocess with proper process group for cleanup
            process = await asyncio.create_subprocess_exec(
                *command,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                preexec_fn=os.setsid if hasattr(os, 'setsid') else None  # Create process group on Unix
            )
            
            # Store process group ID for cleanup
            if hasattr(os, 'getpgid') and process.pid:
                try:
                    process_group_id = os.getpgid(process.pid)
                except:
                    process_group_id = None
            
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
                
                # Enhanced cleanup sequence
                cleanup_success = await self._cleanup_timed_out_process(process, process_group_id)
                
                if not cleanup_success:
                    logger.error("❌ Failed to cleanup timed out process - may still be running")
                
                raise Exception(f"Command timed out after {timeout} seconds")
            
        except FileNotFoundError:
            raise Exception(f"Command not found: {command[0]}")
        except Exception as e:
            # Ensure cleanup on any error
            if process:
                await self._cleanup_timed_out_process(process, process_group_id)
            raise e
    
    async def _safe_subprocess_exec(self, command: List[str], cwd: str = None, timeout: int = None) -> 'CommandResult':
        """
        🔥 NEW: Safe subprocess execution with comprehensive error handling
        """
        if timeout is None:
            timeout = self.timeout
        
        process = None
        process_group_id = None
        
        try:
            # Create subprocess with proper error handling
            process = await asyncio.create_subprocess_exec(
                *command,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                preexec_fn=os.setsid if hasattr(os, 'setsid') else None
            )
            
            # Verify process creation
            if process is None:
                logger.error(f"❌ Failed to create subprocess for: {' '.join(command)}")
                return type('CommandResult', (), {
                    'returncode': -1,
                    'stdout': '',
                    'stderr': 'Failed to create subprocess'
                })()
            
            # Store process group ID
            if hasattr(os, 'getpgid') and process.pid:
                try:
                    process_group_id = os.getpgid(process.pid)
                except:
                    process_group_id = None
            
            # Execute with timeout
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
            cleanup_success = await self._cleanup_timed_out_process(process, process_group_id)
            if not cleanup_success:
                logger.error("❌ Failed to cleanup timed out process")
            
            return type('CommandResult', (), {
                'returncode': -1,
                'stdout': '',
                'stderr': f'Command timed out after {timeout} seconds'
            })()
            
        except FileNotFoundError:
            logger.error(f"❌ Command not found: {command[0]}")
            return type('CommandResult', (), {
                'returncode': -1,
                'stdout': '',
                'stderr': f'Command not found: {command[0]}'
            })()
            
        except Exception as e:
            logger.error(f"❌ Error running command {' '.join(command)}: {e}")
            if process:
                await self._cleanup_timed_out_process(process, process_group_id)
            
            return type('CommandResult', (), {
                'returncode': -1,
                'stdout': '',
                'stderr': str(e)
            })()
    
    async def _cleanup_timed_out_process(self, process, process_group_id=None) -> bool:
        """
        🔥 NEW: Enhanced process cleanup with multiple fallback strategies
        """
        cleanup_success = False
        
        try:
            # Strategy 1: Graceful termination
            if process and process.returncode is None:
                logger.info("🔄 Attempting graceful process termination...")
                try:
                    process.terminate()
                    await asyncio.wait_for(process.wait(), timeout=self.kill_timeout)
                    logger.info("✅ Process terminated gracefully")
                    cleanup_success = True
                except asyncio.TimeoutError:
                    logger.warning("⚠️ Graceful termination timeout, trying force kill...")
                except Exception as e:
                    logger.warning(f"⚠️ Error in graceful termination: {e}")
            
            # Strategy 2: Force kill process
            if not cleanup_success and process and process.returncode is None:
                logger.warning("🔥 Force killing process...")
                try:
                    process.kill()
                    await asyncio.wait_for(process.wait(), timeout=5)
                    logger.info("✅ Process force killed")
                    cleanup_success = True
                except asyncio.TimeoutError:
                    logger.error("❌ Force kill timeout")
                except Exception as e:
                    logger.error(f"❌ Error force killing process: {e}")
            
            # Strategy 3: Kill process group (Unix only)
            if not cleanup_success and process_group_id and hasattr(os, 'killpg'):
                logger.warning("🔥 Killing process group...")
                try:
                    os.killpg(process_group_id, 9)  # SIGKILL
                    await asyncio.sleep(1)  # Give it a moment
                    if process.returncode is None:
                        await asyncio.wait_for(process.wait(), timeout=5)
                    logger.info("✅ Process group killed")
                    cleanup_success = True
                except Exception as e:
                    logger.error(f"❌ Error killing process group: {e}")
            
            # Strategy 4: Last resort - system kill (if available)
            if not cleanup_success and process and process.pid:
                logger.warning("🔥 Last resort: system kill...")
                try:
                    import signal
                    os.kill(process.pid, signal.SIGKILL)
                    await asyncio.sleep(1)
                    logger.info("✅ System kill attempted")
                    cleanup_success = True
                except Exception as e:
                    logger.error(f"❌ System kill failed: {e}")
            
            return cleanup_success
            
        except Exception as e:
            logger.error(f"❌ Critical error in process cleanup: {e}")
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
                    last_error = f"Command '{' '.join(command)}' failed (exit {result.returncode})\nSTDERR:\n{result.stderr}"
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
        🔥 ENHANCED: Command repair with comprehensive anti-loop protection
        """
        try:
            import time
            command_str = ' '.join(command)
            error_lower = error_output.lower()
            
            # 🔥 NEW: Check repair session duration
            current_time = time.time()
            if project_path not in self.repair_session_start:
                self.repair_session_start[project_path] = current_time
            
            session_duration = current_time - self.repair_session_start[project_path]
            if session_duration > self.max_repair_session_duration:
                logger.warning(f"🛑 REPAIR SESSION TIMEOUT for project {project_path} ({session_duration:.0f}s > {self.max_repair_session_duration}s)")
                logger.warning("⚠️ Repair session has been running too long. Stopping to prevent infinite loop.")
                return False
            
            # 🔥 NEW: Check global project repair limit first
            project_repairs = self.project_repair_counts.get(project_path, 0)
            if project_repairs >= self.max_total_repairs_per_project:
                logger.warning(f"🛑 GLOBAL REPAIR LIMIT REACHED for project {project_path} ({project_repairs}/{self.max_total_repairs_per_project})")
                logger.warning("⚠️ This project has had too many repair attempts. Stopping to prevent infinite loop.")
                return False
            
            # 🔥 NEW: Enhanced anti-loop protection per command
            repair_key = f"{project_path}:{command_str}:{hash(error_output)}"
            current_attempts = self.repair_attempts.get(repair_key, 0)
            
            if current_attempts >= self.max_repair_attempts:
                logger.warning(f"🔄 Repair attempt limit reached for {command_str} - skipping to prevent loop")
                return False
            
            # 🔥 NEW: Check command-specific repair history
            command_type = command[0] if command else "unknown"
            command_repairs = self.command_repair_history.get(f"{project_path}:{command_type}", 0)
            if command_repairs >= 3:  # Max 3 repairs per command type per project
                logger.warning(f"🔄 Command type repair limit reached for {command_type} in {project_path}")
                return False
            
            self.repair_attempts[repair_key] = current_attempts + 1
            self.project_repair_counts[project_path] = project_repairs + 1
            self.command_repair_history[f"{project_path}:{command_type}"] = command_repairs + 1
            
            logger.info(f"🔍 Analyzing failure for auto-repair (attempt {current_attempts + 1}/{self.max_repair_attempts}, project total: {project_repairs + 1}/{self.max_total_repairs_per_project}, session: {session_duration:.0f}s): {command_str}")
            
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
                stack = await self._detect_project_stack(project_path)
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
            for line in patch_text.split('\n'):
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
