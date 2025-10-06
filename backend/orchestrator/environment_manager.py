"""
Universal Environment Manager for Auto-Setup & Self-Healing
Detects and fixes environment issues across all project stacks
"""
import os
import json
import logging
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

@dataclass
class EnvironmentFix:
    """Represents a fix to apply for an environment issue"""
    issue_type: EnvironmentIssue
    description: str
    commands: List[List[str]]  # List of commands to run
    files_to_create: Dict[str, str] = None  # filepath -> content
    success_indicators: List[str] = None  # Files/dirs that should exist after fix

class EnvironmentManager:
    """Universal environment detection and auto-repair system"""
    
    def __init__(self):
        self.stack_detectors = {
            "laravel": self._detect_laravel_issues,
            "vue": self._detect_vue_issues, 
            "react": self._detect_react_issues,
            "python": self._detect_python_issues,
            "node": self._detect_node_issues
        }
        
    async def detect_and_fix_environment(self, project_path: str, stack: str) -> List[str]:
        """
        Main method: detects environment issues and applies fixes
        Returns list of fixes applied
        """
        if not os.path.exists(project_path):
            logger.error(f"Project path does not exist: {project_path}")
            return []
            
        logger.info(f"🔍 Detecting environment issues for {stack} project at {project_path}")
        
        # Detect issues
        issues = await self._detect_issues(project_path, stack)
        if not issues:
            logger.info("✅ No environment issues detected")
            return []
        
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
        
        return fixes_applied
    
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
    
    # ========== STACK-SPECIFIC DETECTORS ==========
    
    async def _detect_laravel_issues(self, project_path: str) -> List[Tuple[EnvironmentIssue, EnvironmentFix]]:
        """Detect Laravel/PHP specific issues with enhanced coverage"""
        issues = []
        project_root = Path(project_path)
        
        # Check vendor directory
        if not (project_root / "vendor").exists():
            composer_json = project_root / "composer.json"
            if composer_json.exists():
                issues.append((
                    EnvironmentIssue.MISSING_VENDOR,
                    EnvironmentFix(
                        issue_type=EnvironmentIssue.MISSING_VENDOR,
                        description="Install Composer dependencies",
                        commands=[["composer", "install", "--no-interaction", "--no-progress"]],
                        success_indicators=["vendor/autoload.php"]
                    )
                ))
        
        # Check artisan file
        if not (project_root / "artisan").exists():
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
        
        # Check phpstan.neon.dist for static analysis
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
        
        # Check if bootstrap/app.php exists (Laravel structure validation)
        if not (project_root / "bootstrap").exists():
            issues.append((
                EnvironmentIssue.MISSING_CONFIG_FILE,
                EnvironmentFix(
                    issue_type=EnvironmentIssue.MISSING_CONFIG_FILE,
                    description="Create Laravel bootstrap structure",
                    commands=[],
                    files_to_create={
                        "bootstrap/app.php": self._get_bootstrap_app_stub()
                    },
                    success_indicators=["bootstrap/app.php"]
                )
            ))
        
        # Check composer.json scripts
        composer_json = project_root / "composer.json"
        if composer_json.exists():
            scripts_needed = await self._check_laravel_composer_scripts(composer_json)
            if scripts_needed:
                issues.append((
                    EnvironmentIssue.MISSING_SCRIPTS,
                    EnvironmentFix(
                        issue_type=EnvironmentIssue.MISSING_SCRIPTS,
                        description=f"Add missing composer scripts: {', '.join(scripts_needed.keys())}",
                        commands=[],
                        files_to_create={"composer.json": "UPDATE_SCRIPTS"},
                        success_indicators=[]
                    )
                ))
        
        # Check .env file
        if not (project_root / ".env").exists() and (project_root / ".env.example").exists():
            issues.append((
                EnvironmentIssue.MISSING_CONFIG_FILE,
                EnvironmentFix(
                    issue_type=EnvironmentIssue.MISSING_CONFIG_FILE,
                    description="Create .env file from .env.example",
                    commands=[["cp", ".env.example", ".env"]],
                    success_indicators=[".env"]
                )
            ))
        
        return issues
    
    async def _detect_vue_issues(self, project_path: str) -> List[Tuple[EnvironmentIssue, EnvironmentFix]]:
        """Detect Vue.js specific issues"""
        issues = []
        project_root = Path(project_path)
        
        # Check node_modules
        if not (project_root / "node_modules").exists():
            package_json = project_root / "package.json"
            if package_json.exists():
                # Determine package manager
                yarn_lock = project_root / "yarn.lock"
                npm_lock = project_root / "package-lock.json"
                
                if yarn_lock.exists():
                    cmd = ["yarn", "install"]
                else:
                    cmd = ["npm", "install"]
                    
                issues.append((
                    EnvironmentIssue.MISSING_NODE_MODULES,
                    EnvironmentFix(
                        issue_type=EnvironmentIssue.MISSING_NODE_MODULES,
                        description="Install Node.js dependencies",
                        commands=[cmd],
                        success_indicators=["node_modules"]
                    )
                ))
        
        # Check dev dependencies for testing
        package_json = project_root / "package.json"
        if package_json.exists():
            missing_dev_deps = await self._check_vue_dev_dependencies(package_json)
            if missing_dev_deps:
                yarn_lock = project_root / "yarn.lock"
                base_cmd = ["yarn", "add", "-D"] if yarn_lock.exists() else ["npm", "install", "--save-dev"]
                
                issues.append((
                    EnvironmentIssue.MISSING_DEPENDENCIES,
                    EnvironmentFix(
                        issue_type=EnvironmentIssue.MISSING_DEPENDENCIES,
                        description=f"Install Vue dev dependencies: {', '.join(missing_dev_deps)}",
                        commands=[base_cmd + missing_dev_deps],
                        success_indicators=[]
                    )
                ))
        
        return issues
    
    async def _detect_react_issues(self, project_path: str) -> List[Tuple[EnvironmentIssue, EnvironmentFix]]:
        """Detect React specific issues (similar to Vue but with React-specific deps)"""
        issues = []
        project_root = Path(project_path)
        
        # Check node_modules (same as Vue)
        if not (project_root / "node_modules").exists():
            package_json = project_root / "package.json"
            if package_json.exists():
                yarn_lock = project_root / "yarn.lock"
                cmd = ["yarn", "install"] if yarn_lock.exists() else ["npm", "install"]
                    
                issues.append((
                    EnvironmentIssue.MISSING_NODE_MODULES,
                    EnvironmentFix(
                        issue_type=EnvironmentIssue.MISSING_NODE_MODULES,
                        description="Install Node.js dependencies",
                        commands=[cmd],
                        success_indicators=["node_modules"]
                    )
                ))
        
        # Check React dev dependencies
        package_json = project_root / "package.json"
        if package_json.exists():
            missing_dev_deps = await self._check_react_dev_dependencies(package_json)
            if missing_dev_deps:
                yarn_lock = project_root / "yarn.lock"
                base_cmd = ["yarn", "add", "-D"] if yarn_lock.exists() else ["npm", "install", "--save-dev"]
                
                issues.append((
                    EnvironmentIssue.MISSING_DEPENDENCIES,
                    EnvironmentFix(
                        issue_type=EnvironmentIssue.MISSING_DEPENDENCIES,
                        description=f"Install React dev dependencies: {', '.join(missing_dev_deps)}",
                        commands=[base_cmd + missing_dev_deps],
                        success_indicators=[]
                    )
                ))
        
        return issues
    
    async def _detect_python_issues(self, project_path: str) -> List[Tuple[EnvironmentIssue, EnvironmentFix]]:
        """Detect Python specific issues"""
        issues = []
        project_root = Path(project_path)
        
        # Check requirements.txt and dependencies
        requirements_txt = project_root / "requirements.txt"
        if requirements_txt.exists():
            # Check if packages are installed (simplified check)
            try:
                import subprocess
                result = subprocess.run(["pip", "check"], capture_output=True, text=True)
                if result.returncode != 0:
                    issues.append((
                        EnvironmentIssue.MISSING_DEPENDENCIES,
                        EnvironmentFix(
                            issue_type=EnvironmentIssue.MISSING_DEPENDENCIES,
                            description="Install Python dependencies from requirements.txt",
                            commands=[["pip", "install", "-r", "requirements.txt"]],
                            success_indicators=[]
                        )
                    ))
            except Exception:
                # If pip check fails, assume we need to install
                issues.append((
                    EnvironmentIssue.MISSING_DEPENDENCIES,
                    EnvironmentFix(
                        issue_type=EnvironmentIssue.MISSING_DEPENDENCIES,
                        description="Install Python dependencies from requirements.txt",
                        commands=[["pip", "install", "-r", "requirements.txt"]],
                        success_indicators=[]
                    )
                ))
        
        return issues
    
    async def _detect_node_issues(self, project_path: str) -> List[Tuple[EnvironmentIssue, EnvironmentFix]]:
        """Detect Node.js specific issues"""
        # For now, same as Vue/React for Node projects
        return await self._detect_vue_issues(project_path)
    
    # ========== HELPER METHODS ==========
    
    async def _apply_fix(self, project_path: str, fix: EnvironmentFix) -> bool:
        """Apply a specific fix"""
        try:
            # Execute commands
            for command in fix.commands:
                logger.info(f"Executing: {' '.join(command)}")
                import subprocess
                result = subprocess.run(
                    command, 
                    cwd=project_path, 
                    capture_output=True, 
                    text=True,
                    timeout=300
                )
                
                if result.returncode != 0:
                    logger.error(f"Command failed: {result.stderr}")
                    return False
            
            # Create files
            if fix.files_to_create:
                for filepath, content in fix.files_to_create.items():
                    if content == "UPDATE_SCRIPTS":
                        await self._update_composer_scripts(project_path, filepath)
                    else:
                        full_path = Path(project_path) / filepath
                        full_path.parent.mkdir(parents=True, exist_ok=True)
                        full_path.write_text(content)
                        
                        # Make artisan executable
                        if filepath == "artisan":
                            os.chmod(full_path, 0o755)
            
            # Verify success indicators
            if fix.success_indicators:
                for indicator in fix.success_indicators:
                    indicator_path = Path(project_path) / indicator
                    if not indicator_path.exists():
                        logger.warning(f"Success indicator not found: {indicator}")
                        return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error applying fix: {e}")
            return False
    
    async def _check_laravel_composer_scripts(self, composer_json_path: Path) -> Dict[str, str]:
        """Check which Laravel composer scripts are missing"""
        required_scripts = {
            "test": "pest",
            "phpstan": "phpstan analyse app/",
            "pint": "pint"
        }
        
        try:
            with open(composer_json_path, 'r') as f:
                composer_data = json.load(f)
            
            existing_scripts = composer_data.get('scripts', {})
            missing_scripts = {}
            
            for script_name, script_command in required_scripts.items():
                if script_name not in existing_scripts:
                    missing_scripts[script_name] = script_command
            
            return missing_scripts
            
        except Exception as e:
            logger.error(f"Error checking composer scripts: {e}")
            return {}
    
    async def _check_vue_dev_dependencies(self, package_json_path: Path) -> List[str]:
        """Check which Vue dev dependencies are missing"""
        required_deps = [
            "vitest", "@vue/test-utils", "eslint", "jsdom", "@vitejs/plugin-vue"
        ]
        
        try:
            with open(package_json_path, 'r') as f:
                package_data = json.load(f)
            
            all_deps = {**package_data.get('dependencies', {}), **package_data.get('devDependencies', {})}
            missing_deps = [dep for dep in required_deps if dep not in all_deps]
            
            return missing_deps
            
        except Exception as e:
            logger.error(f"Error checking Vue dev dependencies: {e}")
            return []
    
    async def _check_react_dev_dependencies(self, package_json_path: Path) -> List[str]:
        """Check which React dev dependencies are missing"""
        required_deps = [
            "@testing-library/jest-dom", "@testing-library/react", 
            "@testing-library/user-event", "eslint", "eslint-plugin-react"
        ]
        
        try:
            with open(package_json_path, 'r') as f:
                package_data = json.load(f)
            
            all_deps = {**package_data.get('dependencies', {}), **package_data.get('devDependencies', {})}
            missing_deps = [dep for dep in required_deps if dep not in all_deps]
            
            return missing_deps
            
        except Exception as e:
            logger.error(f"Error checking React dev dependencies: {e}")
            return []
    
    async def _update_composer_scripts(self, project_path: str, composer_json_path: str) -> None:
        """Update composer.json with missing scripts"""
        try:
            full_path = Path(project_path) / composer_json_path
            with open(full_path, 'r') as f:
                composer_data = json.load(f)
            
            # Get missing scripts
            missing_scripts = await self._check_laravel_composer_scripts(full_path)
            
            # Update scripts section
            if 'scripts' not in composer_data:
                composer_data['scripts'] = {}
            
            composer_data['scripts'].update(missing_scripts)
            
            # Write back
            with open(full_path, 'w') as f:
                json.dump(composer_data, f, indent=2)
            
            logger.info(f"Updated composer.json with scripts: {list(missing_scripts.keys())}")
            
        except Exception as e:
            logger.error(f"Error updating composer scripts: {e}")
    
    def _get_artisan_stub(self) -> str:
        """Get Laravel artisan file content"""
        return '''#!/usr/bin/env php
<?php

define('LARAVEL_START', microtime(true));

// Register The Auto Loader
require __DIR__.'/vendor/autoload.php';

// Bootstrap Laravel and handle the command
$app = require_once __DIR__.'/bootstrap/app.php';
$kernel = $app->make(Illuminate\\Contracts\\Console\\Kernel::class);
$status = $kernel->handle(
    $input = new Symfony\\Component\\Console\\Input\\ArgvInput,
    new Symfony\\Component\\Console\\Output\\ConsoleOutput
);
$kernel->terminate($input, $status);
exit($status);
'''