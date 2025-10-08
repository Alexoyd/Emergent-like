"""
🔥 ENHANCED Universal Environment Manager for Auto-Setup & Self-Healing
Detects and fixes environment issues across all project stacks with robust Laravel validation
"""
import os
import json
import logging
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class EnvironmentIssue(Enum):
    """Types of environment issues that can be auto-fixed"""
    MISSING_DEPENDENCIES = "missing_dependencies"
    MISSING_VENDOR = "missing_vendor"
    MISSING_NODE_MODULES = "missing_node_modules"
    MISSING_SCRIPTS = "missing_scripts"
    MISSING_CONFIG_FILE = "missing_config_file"
    INVALID_COMMAND = "invalid_command"
    PATH_NOT_FOUND = "path_not_found"
    PERMISSION_ERROR = "permission_error"
    CORRUPTED_INSTALLATION = "corrupted_installation"
    INCOMPLETE_PROJECT_STRUCTURE = "incomplete_project_structure"

@dataclass
class EnvironmentFix:
    """Represents a fix to apply for an environment issue"""
    issue_type: EnvironmentIssue
    description: str
    commands: List[List[str]]  # List of commands to run
    files_to_create: Dict[str, str] = None  # filepath -> content
    success_indicators: List[str] = None  # Files/dirs that should exist after fix

class EnvironmentManager:
    """🔥 ENHANCED Universal environment detection and auto-repair system"""
    
    def __init__(self):
        self.stack_detectors = {
            "laravel": self._detect_laravel_issues,
            "vue": self._detect_vue_issues, 
            "react": self._detect_react_issues,
            "python": self._detect_python_issues,
            "node": self._detect_node_issues
        }
        # 🔥 NEW: Command timeout for environment operations
        self.command_timeout = 180  # 3 minutes for package installations
        
    async def detect_and_fix_environment(self, project_path: str, stack: str) -> List[str]:
        """
        🔥 ENHANCED: Main method with comprehensive environment validation
        """
        if not os.path.exists(project_path):
            logger.error(f"Project path does not exist: {project_path}")
            return []
        
        try:
            logger.info(f"🔍 Comprehensive environment analysis for {stack} project at {project_path}")
            
            # 🔥 NEW: Pre-validation - check if this is actually a valid project of declared stack
            if not await self._validate_project_type(project_path, stack):
                logger.error(f"❌ Project validation failed - {project_path} is not a valid {stack} project")
                return ["project_validation_failed"]
            
            # Detect issues
            issues = await self._detect_issues(project_path, stack)
            if not issues:
                # 🔥 NEW: Even if no issues detected, run final health check
                health_ok = await self._final_health_check(project_path, stack)
                if health_ok:
                    logger.info("✅ No environment issues detected - project is healthy")
                    return []
                else:
                    logger.warning("⚠️ No specific issues detected but final health check failed")
                    return ["health_check_failed"]
        
            # Apply fixes
            fixes_applied = []
            for issue, fix in issues:
                logger.info(f"🔧 Applying fix for {issue.value}: {fix.description}")
                success = await self._apply_fix(project_path, fix)
                if success:
                    fixes_applied.append(f"{issue.value}: {fix.description}")
                    logger.info(f"✅ Successfully fixed {issue.value}")
                else:
                    logger.warning(f"❌ Failed to fix {issue.value}")
                    fixes_applied.append(f"{issue.value}: FAILED - {fix.description}")
        
            # 🔥 NEW: Post-fix validation
            if fixes_applied:
                logger.info("🏥 Running post-fix health check...")
                health_ok = await self._final_health_check(project_path, stack)
                if not health_ok:
                    fixes_applied.append("post_fix_health_check: FAILED")
        
            return fixes_applied
        
        except Exception as e:
            logger.error(f"Critical error in environment detection: {e}")
            return [f"environment_error: {str(e)}"]
    
    async def _validate_project_type(self, project_path: str, declared_stack: str) -> bool:
        """
        🔥 NEW: Validate that the project is actually of the declared stack type
        """
        try:
            project_root = Path(project_path)
            
            if declared_stack == "laravel":
                # Laravel must have composer.json AND artisan AND some Laravel-specific structure
                required_files = ["composer.json", "artisan"]
                for req_file in required_files:
                    if not (project_root / req_file).exists():
                        logger.warning(f"❌ Laravel project missing: {req_file}")
                        return False
                
                # Validate composer.json actually references Laravel
                try:
                    composer_json = project_root / "composer.json"
                    with open(composer_json, 'r') as f:
                        composer_data = json.load(f)
                    
                    require = composer_data.get("require", {})
                    if not any(pkg.startswith("laravel/") or pkg.startswith("illuminate/") 
                              for pkg in require.keys()):
                        logger.warning("❌ composer.json doesn't reference Laravel packages")
                        return False
                
                except Exception as e:
                    logger.warning(f"❌ Invalid composer.json: {e}")
                    return False
                
                return True
                
            elif declared_stack in ["vue", "react", "node"]:
                # Node-based projects need package.json
                if not (project_root / "package.json").exists():
                    logger.warning(f"❌ {declared_stack} project missing package.json")
                    return False
                return True
                
            elif declared_stack == "python":
                # Python projects should have requirements.txt or pyproject.toml
                if not any((project_root / f).exists() for f in ["requirements.txt", "pyproject.toml", "setup.py"]):
                    logger.warning(f"❌ Python project missing dependency file")
                    return False
                return True
            
            # Unknown or generic stack - accept as valid
            return True
            
        except Exception as e:
            logger.error(f"Error validating project type: {e}")
            return False
    
    async def _final_health_check(self, project_path: str, stack: str) -> bool:
        """
        🔥 NEW: Final comprehensive health check to ensure environment is actually working
        """
        try:
            logger.info(f"🏥 Final health check for {stack} project...")
            project_root = Path(project_path)
            
            if stack == "laravel":
                # Check Laravel health indicators
                health_indicators = [
                    ("vendor/autoload.php", "Composer autoloader"),
                    ("bootstrap/app.php", "Laravel bootstrap"),
                    ("config", "Configuration directory"),
                    ("app", "Application directory"),
                ]
                
                for indicator, description in health_indicators:
                    if not (project_root / indicator).exists():
                        logger.warning(f"❌ Health check failed: Missing {description}")
                        return False
                
                # Test if composer autoloader actually works
                try:
                    result = await self._run_command_with_timeout(
                        ["php", "-r", "require 'vendor/autoload.php'; echo 'OK';"],
                        cwd=project_path,
                        timeout=10
                    )
                    if result.returncode != 0 or "OK" not in result.stdout:
                        logger.warning(f"❌ Composer autoloader test failed")
                        return False
                except:
                    logger.warning(f"❌ Could not test composer autoloader")
                    return False
                
                # Test if artisan is executable
                try:
                    result = await self._run_command_with_timeout(
                        ["php", "artisan", "--version"],
                        cwd=project_path,
                        timeout=15
                    )
                    if result.returncode != 0:
                        logger.warning(f"❌ Artisan test failed: {result.stderr}")
                        return False
                except:
                    logger.warning(f"❌ Could not test artisan command")
                    return False
                
                logger.info("✅ Laravel health check passed")
                return True
                
            elif stack in ["vue", "react", "node"]:
                # Basic Node.js health check
                return (project_root / "package.json").exists()
                
            elif stack == "python":
                # Basic Python health check  
                return any((project_root / f).exists() for f in ["requirements.txt", "pyproject.toml", "setup.py"])
            
            # For other stacks, basic existence check
            return project_root.exists()
            
        except Exception as e:
            logger.error(f"Error in final health check: {e}")
            return False
    
    async def _detect_issues(self, project_path: str, stack: str) -> List[Tuple[EnvironmentIssue, EnvironmentFix]]:
        """Detect environment issues for specific stack"""
        issues = []
        
        # Use stack-specific detector
        if stack in self.stack_detectors:
            stack_issues = await self.stack_detectors[stack](project_path)
            issues.extend(stack_issues)
        
        # Universal checks (apply to all stacks)
        universal_issues = await self._detect_universal_issues(project_path)
        issues.extend(universal_issues)
        
        return issues
    
    async def _detect_universal_issues(self, project_path: str) -> List[Tuple[EnvironmentIssue, EnvironmentFix]]:
        """Universal environment checks that apply to all projects"""
        issues = []
        project_root = Path(project_path)
        
        # Check git initialization
        if not (project_root / ".git").exists():
            issues.append((
                EnvironmentIssue.MISSING_CONFIG_FILE,
                EnvironmentFix(
                    issue_type=EnvironmentIssue.MISSING_CONFIG_FILE,
                    description="Initialize git repository",
                    commands=[["git", "init"]],
                    success_indicators=[".git"]
                )
            ))
        
        return issues
    
    # ========== 🔥 ENHANCED STACK-SPECIFIC DETECTORS ==========
    
    async def _detect_laravel_issues(self, project_path: str) -> List[Tuple[EnvironmentIssue, EnvironmentFix]]:
        """🔥 ENHANCED Laravel/PHP issue detection with complete project validation"""
        issues = []
        project_root = Path(project_path)
        
        # 🔥 NEW: Check if this is a complete Laravel installation
        is_complete_laravel = await self._is_complete_laravel_installation(project_root)
        
        if not is_complete_laravel:
            # This is not a complete Laravel installation - need to create one
            issues.append((
                EnvironmentIssue.INCOMPLETE_PROJECT_STRUCTURE,
                EnvironmentFix(
                    issue_type=EnvironmentIssue.INCOMPLETE_PROJECT_STRUCTURE,
                    description="Create complete Laravel project installation",
                    commands=[],  # Will be handled by LaravelHandler
                    files_to_create={},  # Will be handled by LaravelHandler
                    success_indicators=["artisan", "vendor/autoload.php", "bootstrap/app.php", "config/app.php"]
                )
            ))
            return issues  # Return early - need complete reinstallation
        
        # 1. Check vendor directory and autoloader
        if not (project_root / "vendor").exists():
            composer_json = project_root / "composer.json"
            if composer_json.exists():
                issues.append((
                    EnvironmentIssue.MISSING_VENDOR,
                    EnvironmentFix(
                        issue_type=EnvironmentIssue.MISSING_VENDOR,
                        description="Install Composer dependencies",
                        commands=[["composer", "install", "--no-interaction", "--no-progress"]],
                        success_indicators=["vendor/autoload.php", "vendor/composer"]
                    )
                ))
        else:
            # Vendor exists but check if it's corrupted
            autoload_file = project_root / "vendor" / "autoload.php"
            if not autoload_file.exists():
                issues.append((
                    EnvironmentIssue.CORRUPTED_INSTALLATION,
                    EnvironmentFix(
                        issue_type=EnvironmentIssue.CORRUPTED_INSTALLATION,
                        description="Reinstall corrupted Composer dependencies",
                        commands=[
                            ["rm", "-rf", "vendor"],
                            ["composer", "install", "--no-interaction", "--no-progress"]
                        ],
                        success_indicators=["vendor/autoload.php"]
                    )
                ))
        
        # 2. Check artisan file exists and is executable
        artisan_file = project_root / "artisan"
        if not artisan_file.exists():
            issues.append((
                EnvironmentIssue.MISSING_CONFIG_FILE,
                EnvironmentFix(
                    issue_type=EnvironmentIssue.MISSING_CONFIG_FILE,
                    description="Create Laravel artisan file",
                    commands=[],
                    files_to_create={
                        "artisan": self._get_artisan_stub(),
                    },
                    success_indicators=["artisan"]
                )
            ))
        elif not os.access(artisan_file, os.X_OK):
            # Make artisan executable
            issues.append((
                EnvironmentIssue.PERMISSION_ERROR,
                EnvironmentFix(
                    issue_type=EnvironmentIssue.PERMISSION_ERROR,
                    description="Make artisan executable",
                    commands=[["chmod", "+x", "artisan"]],
                    success_indicators=[]
                )
            ))
        
        # 3. Check Laravel directory structure
        required_laravel_dirs = ["app", "bootstrap", "config", "routes"]
        missing_dirs = []
        for req_dir in required_laravel_dirs:
            if not (project_root / req_dir).exists():
                missing_dirs.append(req_dir)
        
        if missing_dirs:
            files_to_create = {}
            
            # Create essential Laravel structure
            for missing_dir in missing_dirs:
                if missing_dir == "app":
                    files_to_create["app/Http/Controllers/.gitkeep"] = ""
                    files_to_create["app/Models/.gitkeep"] = ""
                elif missing_dir == "bootstrap":
                    files_to_create["bootstrap/app.php"] = self._get_bootstrap_app_stub()
                elif missing_dir == "config":
                    files_to_create["config/app.php"] = self._get_config_app_stub()
                elif missing_dir == "routes":
                    files_to_create["routes/web.php"] = self._get_routes_web_stub()
            
            issues.append((
                EnvironmentIssue.INCOMPLETE_PROJECT_STRUCTURE,
                EnvironmentFix(
                    issue_type=EnvironmentIssue.INCOMPLETE_PROJECT_STRUCTURE,
                    description=f"Create missing Laravel directories: {', '.join(missing_dirs)}",
                    commands=[],
                    files_to_create=files_to_create,
                    success_indicators=missing_dirs
                )
            ))
        
        # 4. Check phpstan.neon.dist for static analysis
        if not (project_root / "phpstan.neon.dist").exists():
            issues.append((
                EnvironmentIssue.MISSING_CONFIG_FILE,
                EnvironmentFix(
                    issue_type=EnvironmentIssue.MISSING_CONFIG_FILE,
                    description="Create PHPStan configuration",
                    commands=[],
                    files_to_create={
                        "phpstan.neon.dist": self._get_phpstan_config()
                    },
                    success_indicators=["phpstan.neon.dist"]
                )
            ))
        
        # 5. Check composer.json for required dev dependencies
        await self._check_laravel_dev_dependencies(project_root, issues)
        
        # 6. Check for Pest test configuration
        if not (project_root / "tests").exists():
            issues.append((
                EnvironmentIssue.MISSING_CONFIG_FILE,
                EnvironmentFix(
                    issue_type=EnvironmentIssue.MISSING_CONFIG_FILE,
                    description="Create Laravel test structure",
                    commands=[],
                    files_to_create={
                        "tests/Pest.php": self._get_pest_config(),
                        "tests/Feature/ExampleTest.php": self._get_example_test(),
                        "tests/Unit/.gitkeep": ""
                    },
                    success_indicators=["tests", "tests/Pest.php"]
                )
            ))
        
        return issues
    
    async def _is_complete_laravel_installation(self, project_root: Path) -> bool:
        """🔥 NEW: Check if this is a complete Laravel installation"""
        try:
            # Essential Laravel files that must exist
            essential_files = [
                "artisan",
                "composer.json", 
                "bootstrap/app.php",
                "config/app.php",
                "routes/web.php"
            ]
            
            # Check if all essential files exist
            for file_path in essential_files:
                if not (project_root / file_path).exists():
                    logger.warning(f"❌ Missing essential Laravel file: {file_path}")
                    return False
            
            # Check if composer.json is actually a Laravel project
            try:
                composer_json = project_root / "composer.json"
                with open(composer_json, 'r') as f:
                    composer_data = json.load(f)
                
                require = composer_data.get("require", {})
                if not any(pkg.startswith("laravel/") or pkg.startswith("illuminate/") 
                          for pkg in require.keys()):
                    logger.warning("❌ composer.json doesn't reference Laravel packages")
                    return False
                
                # Check if it has a proper name (not just a skeleton)
                name = composer_data.get("name", "")
                if not name or name.startswith("emergent/"):
                    logger.warning("❌ composer.json has invalid or skeleton name")
                    return False
                    
            except Exception as e:
                logger.warning(f"❌ Invalid composer.json: {e}")
                return False
            
            # Check if artisan is executable and works
            artisan_path = project_root / "artisan"
            if not os.access(artisan_path, os.X_OK):
                logger.warning("❌ Artisan file is not executable")
                return False
            
            # Test if artisan works (basic test)
            try:
                result = await self._run_command_with_timeout(
                    ["php", "artisan", "--version"],
                    cwd=str(project_root),
                    timeout=15
                )
                if result.returncode != 0:
                    logger.warning(f"❌ Artisan test failed: {result.stderr}")
                    return False
                
                logger.info(f"✅ Laravel installation verified: {result.stdout.strip()}")
                return True
                
            except Exception as e:
                logger.warning(f"❌ Artisan test error: {e}")
                return False
                
        except Exception as e:
            logger.warning(f"❌ Laravel installation check error: {e}")
            return False
    
    async def _check_laravel_dev_dependencies(self, project_root: Path, issues: List):
        """Check for required Laravel dev dependencies"""
        try:
            composer_json = project_root / "composer.json"
            if not composer_json.exists():
                return
            
            with open(composer_json, 'r') as f:
                composer_data = json.load(f)
            
            dev_deps = composer_data.get('require-dev', {})
            required_dev_deps = ['pestphp/pest', 'phpstan/phpstan', 'laravel/pint']
            missing_deps = [dep for dep in required_dev_deps if dep not in dev_deps]
            
            if missing_deps:
                issues.append((
                    EnvironmentIssue.MISSING_DEPENDENCIES,
                    EnvironmentFix(
                        issue_type=EnvironmentIssue.MISSING_DEPENDENCIES,
                        description=f"Install missing dev dependencies: {', '.join(missing_deps)}",
                        commands=[["composer", "require", "--dev"] + missing_deps],
                        success_indicators=["vendor/bin/pest", "vendor/bin/phpstan", "vendor/bin/pint"]
                    )
                ))
        
        except Exception as e:
            logger.warning(f"Could not check Laravel dev dependencies: {e}")
    
    async def _detect_vue_issues(self, project_path: str) -> List[Tuple[EnvironmentIssue, EnvironmentFix]]:
        """Detect Vue.js specific issues"""
        issues = []
        project_root = Path(project_path)
        
        if not (project_root / "node_modules").exists():
            package_json = project_root / "package.json"
            if package_json.exists():
                issues.append((
                    EnvironmentIssue.MISSING_NODE_MODULES,
                    EnvironmentFix(
                        issue_type=EnvironmentIssue.MISSING_NODE_MODULES,
                        description="Install Node.js dependencies",
                        commands=[["npm", "install"]],
                        success_indicators=["node_modules"]
                    )
                ))
        
        return issues
    
    async def _detect_react_issues(self, project_path: str) -> List[Tuple[EnvironmentIssue, EnvironmentFix]]:
        """Detect React specific issues"""
        issues = []
        project_root = Path(project_path)
        
        if not (project_root / "node_modules").exists():
            package_json = project_root / "package.json"
            if package_json.exists():
                issues.append((
                    EnvironmentIssue.MISSING_NODE_MODULES,
                    EnvironmentFix(
                        issue_type=EnvironmentIssue.MISSING_NODE_MODULES,
                        description="Install Node.js dependencies",
                        commands=[["npm", "install"]],
                        success_indicators=["node_modules"]
                    )
                ))
        
        return issues
    
    async def _detect_python_issues(self, project_path: str) -> List[Tuple[EnvironmentIssue, EnvironmentFix]]:
        """Detect Python specific issues"""
        issues = []
        # Add Python-specific checks here
        return issues
    
    async def _detect_node_issues(self, project_path: str) -> List[Tuple[EnvironmentIssue, EnvironmentFix]]:
        """Detect Node.js specific issues"""
        issues = []
        project_root = Path(project_path)
        
        if not (project_root / "node_modules").exists():
            package_json = project_root / "package.json"
            if package_json.exists():
                issues.append((
                    EnvironmentIssue.MISSING_NODE_MODULES,
                    EnvironmentFix(
                        issue_type=EnvironmentIssue.MISSING_NODE_MODULES,
                        description="Install Node.js dependencies", 
                        commands=[["npm", "install"]],
                        success_indicators=["node_modules"]
                    )
                ))
        
        return issues
    
    async def _apply_fix(self, project_path: str, fix: EnvironmentFix) -> bool:
        """
        🔥 ENHANCED: Apply a fix with better error handling and validation
        """
        try:
            logger.info(f"Applying fix: {fix.description}")
            
            # 🔥 NEW: Special handling for complete Laravel installation
            if (fix.issue_type == EnvironmentIssue.INCOMPLETE_PROJECT_STRUCTURE and 
                "complete Laravel project installation" in fix.description):
                return await self._create_complete_laravel_installation(project_path)
            
            # 1. Create files if needed
            if fix.files_to_create:
                for file_path, content in fix.files_to_create.items():
                    full_path = Path(project_path) / file_path
                    full_path.parent.mkdir(parents=True, exist_ok=True)
                    full_path.write_text(content)
                    
                    # Make scripts executable
                    if file_path in ["artisan", "manage.py"] or file_path.endswith(".sh"):
                        os.chmod(full_path, 0o755)
                    
                    logger.info(f"✅ Created file: {file_path}")
            
            # 2. Execute commands
            if fix.commands:
                for command in fix.commands:
                    try:
                        result = await self._run_command_with_timeout(
                            command, 
                            cwd=project_path,
                            timeout=self.command_timeout
                        )
                        
                        if result.returncode != 0:
                            logger.error(f"❌ Command failed: {' '.join(command)}")
                            logger.error(f"   STDERR: {result.stderr}")
                            return False
                        else:
                            logger.info(f"✅ Command succeeded: {' '.join(command)}")
                            
                    except Exception as e:
                        logger.error(f"❌ Command error: {' '.join(command)} - {e}")
                        return False
            
            # 3. Verify success indicators
            if fix.success_indicators:
                project_root = Path(project_path)
                for indicator in fix.success_indicators:
                    indicator_path = project_root / indicator
                    if not indicator_path.exists():
                        logger.warning(f"⚠️ Success indicator missing after fix: {indicator}")
                        return False
                    logger.info(f"✅ Success indicator verified: {indicator}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error applying fix: {e}")
            return False
    
    async def _create_complete_laravel_installation(self, project_path: str) -> bool:
        """🔥 NEW: Create a complete Laravel installation using LaravelHandler"""
        try:
            logger.info("🚀 Creating complete Laravel installation...")
            
            # Import LaravelHandler
            from ..stacks.laravel_handler import LaravelHandler
            
            # Create LaravelHandler instance
            laravel_handler = LaravelHandler()
            laravel_handler.logger = logger
            
            # Create complete Laravel project
            await laravel_handler.create_project_skeleton(Path(project_path))
            
            # Install dependencies
            success = await laravel_handler.install_dependencies(Path(project_path))
            
            if success:
                logger.info("✅ Complete Laravel installation created successfully")
                return True
            else:
                logger.error("❌ Laravel installation failed")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error creating Laravel installation: {e}")
            return False
    
    async def _run_command_with_timeout(self, command: List[str], cwd: str, timeout: int = None):
        """Run command with timeout - enhanced version"""
        if timeout is None:
            timeout = self.command_timeout
            
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
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
            logger.error(f"Command timeout: {' '.join(command)}")
            if process:
                process.kill()
                await process.wait()
            raise Exception(f"Command timed out after {timeout} seconds")

    # ========== 🔥 ENHANCED LARAVEL STUBS ==========

    def _get_artisan_stub(self) -> str:
        """Get Laravel artisan file content"""
        return '''#!/usr/bin/env php
<?php

define('LARAVEL_START', microtime(true));

require __DIR__.'/vendor/autoload.php';

$app = require_once __DIR__.'/bootstrap/app.php';

$kernel = $app->make(Illuminate\\Contracts\\Console\\Kernel::class);

$status = $kernel->handle(
    $input = new Symfony\\Component\\Console\\Input\\ArgvInput,
    new Symfony\\Component\\Console\\Output\\ConsoleOutput
);

$kernel->terminate($input, $status);

exit($status);
'''

    def _get_bootstrap_app_stub(self) -> str:
        """Get Laravel bootstrap/app.php content"""
        return '''<?php

$app = new Illuminate\\Foundation\\Application(
    $_ENV['APP_BASE_PATH'] ?? dirname(__DIR__)
);

$app->singleton(
    Illuminate\\Contracts\\Http\\Kernel::class,
    App\\Http\\Kernel::class
);

$app->singleton(
    Illuminate\\Contracts\\Console\\Kernel::class,
    App\\Console\\Kernel::class
);

$app->singleton(
    Illuminate\\Contracts\\Debug\\ExceptionHandler::class,
    App\\Exceptions\\Handler::class
);

return $app;
'''

    def _get_config_app_stub(self) -> str:
        """Get basic Laravel config/app.php"""
        return '''<?php

return [
    'name' => env('APP_NAME', 'Laravel'),
    'env' => env('APP_ENV', 'production'),
    'debug' => (bool) env('APP_DEBUG', false),
    'url' => env('APP_URL', 'http://localhost'),
    'timezone' => 'UTC',
    'locale' => 'en',
    'fallback_locale' => 'en',
    'key' => env('APP_KEY'),
    'cipher' => 'AES-256-CBC',
];
'''

    def _get_routes_web_stub(self) -> str:
        """Get basic Laravel routes/web.php"""
        return '''<?php

use Illuminate\\Support\\Facades\\Route;

Route::get('/', function () {
    return view('welcome');
});
'''

    def _get_phpstan_config(self) -> str:
        """Get PHPStan configuration content"""
        return '''parameters:
    paths:
        - app
    level: 5
    ignoreErrors:
        - '#Call to an undefined method Illuminate\\\\Database\\\\Eloquent\\\\Builder#'
        - '#Call to an undefined method Illuminate\\\\Database\\\\Eloquent\\\\Collection#'
    excludePaths:
        - 'vendor/*'
        - 'bootstrap/cache/*'
        - 'storage/*'
'''

    def _get_pest_config(self) -> str:
        """Get Pest configuration content"""
        return '''<?php

use Tests\\TestCase;
use Illuminate\\Foundation\\Testing\\RefreshDatabase;

uses(TestCase::class, RefreshDatabase::class)->in('Feature');
uses(TestCase::class)->in('Unit');
'''

    def _get_example_test(self) -> str:
        """Get example Pest test"""
        return '''<?php

test('application returns a successful response', function () {
    $response = $this->get('/');
    $response->assertStatus(200);
});

test('basic example', function () {
    expect(true)->toBeTrue();
});
'''
