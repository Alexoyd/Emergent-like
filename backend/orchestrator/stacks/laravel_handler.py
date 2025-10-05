# stacks/laravel_handler.py
from __future__ import annotations
from pathlib import Path
from typing import Optional, List
import json
import re

from .base_handler import StackHandler
from .registry import StackRegistry
from ..utils import json_utils

class LaravelHandler(StackHandler):
    name = "laravel"
    default_test_command: List[str] = ["vendor/bin/pest", "-q"]

    @staticmethod
    def sanitize_composer_name(name: Optional[str]) -> str:
        """Validate/correct a Composer package name to vendor/project."""
        if not name or not isinstance(name, str):
            return "default/project"
        split_camel = re.sub(r"([a-z0-9])([A-Z])", r"\1-\2", name)
        sanitized = split_camel.replace(" ", "-").lower()
        sanitized = re.sub(r"[^a-z0-9._/-]+", "-", sanitized)
        sanitized = re.sub(r"-+", "-", sanitized)
        parts = sanitized.split("/", 1)
        if len(parts) == 1:
            vendor, project = "default", parts[0]
        else:
            vendor, project = parts[0], parts[1]
        vendor = re.sub(r"^[^a-z0-9]+", "", vendor)
        vendor = re.sub(r"[^a-z0-9]+$", "", vendor)
        project = re.sub(r"^[^a-z0-9]+", "", project)
        project = re.sub(r"[^a-z0-9]+$", "", project)
        if not vendor:
            vendor = "default"
        if not project:
            project = "project"
        normalized = f"{vendor}/{project}"
        if re.match(r"^[a-z0-9]([_.-]?[a-z0-9]+)*/[a-z0-9](([_.]|-{1,2})?[a-z0-9]+)*$", normalized):
            return normalized
        return "default/project"

    async def create_project_skeleton(self, code_path: Path, project_name: Optional[str] = None) -> None:
        """Create a real Laravel project using composer create-project"""
        import subprocess
        import asyncio
        import tempfile
        import shutil
        
        try:
            # Create real Laravel project in temporary directory
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_project_path = Path(temp_dir) / "laravel_project"
                
                if self.logger:
                    self.logger.info("Creating Laravel project via composer create-project...")
                
                # Run composer create-project
                create_cmd = [
                    "composer", "create-project", 
                    "laravel/laravel", str(temp_project_path),
                    "--prefer-dist", "--no-dev", "--no-install"
                ]
                
                process = await asyncio.create_subprocess_exec(
                    *create_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=temp_dir
                )
                
                stdout, stderr = await process.communicate()
                
                if process.returncode == 0:
                    # Success - copy files to target directory
                    if temp_project_path.exists():
                        # Ensure target directory exists
                        code_path.mkdir(parents=True, exist_ok=True)
                        
                        # Copy all files from temp to target
                        for item in temp_project_path.iterdir():
                            if item.is_dir():
                                shutil.copytree(item, code_path / item.name, dirs_exist_ok=True)
                            else:
                                shutil.copy2(item, code_path / item.name)
                        
                        if self.logger:
                            self.logger.info(f"✅ Real Laravel project created at {code_path}")
                        
                        # Create phpstan.neon.dist for static analysis
                        phpstan_config = code_path / "phpstan.neon.dist"
                        phpstan_config.write_text("""parameters:
    paths:
        - app
    level: 5
    ignoreErrors:
        - '#Call to an undefined method Illuminate\\\\Database\\\\Eloquent\\\\Builder#'
""")
                        
                        return
                        
                else:
                    if self.logger:
                        self.logger.warning(f"Composer create-project failed: {stderr.decode()}")
                        
        except Exception as e:
            if self.logger:
                self.logger.warning(f"Failed to create real Laravel project: {e}")
        
        # Fallback to skeleton if composer create-project fails
        await self._create_minimal_skeleton(code_path, project_name)
    
    async def _create_minimal_skeleton(self, code_path: Path, project_name: Optional[str] = None) -> None:
        """Fallback: create minimal Laravel skeleton"""
        if self.logger:
            self.logger.info("Creating minimal Laravel skeleton as fallback")
            
        dirs = [
            "app/Http/Controllers",
            "app/Models", 
            "routes",
            "tests/Feature",
            "tests/Unit",
            "config",
            "public",
        ]
        for d in dirs:
            (code_path / d).mkdir(parents=True, exist_ok=True)

        files = {
            "routes/web.php": "<?php\n\nuse Illuminate\\Support\\Facades\\Route;\n\nRoute::get('/', function () {\n    return 'Hello World!';\n});\n",
            "composer.json": f'{{\n    "name": "emergent/{project_name or "project"}",\n    "type": "project",\n    "require": {{\n        "php": "^8.1",\n        "laravel/framework": "^10.0"\n    }},\n    "require-dev": {{\n        "pestphp/pest": "^2.0",\n        "phpstan/phpstan": "^1.0",\n        "laravel/pint": "^1.0"\n    }},\n    "autoload": {{\n        "psr-4": {{\n            "App\\\\": "app/"\n        }}\n    }}\n}}',
            "phpstan.neon.dist": "parameters:\n    paths:\n        - app\n    level: 5\n",
        }
        
        for fp, content in files.items():
            p = code_path / fp
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)

    async def install_dependencies(self, code_path: Path) -> bool:
        # sanitize composer.json if exists
        composer_file = code_path / "composer.json"
        if composer_file.exists():
            try:
                composer_data = json.loads(composer_file.read_text())
                original_name = composer_data.get("name")
                corrected = self.sanitize_composer_name(original_name)
                if original_name != corrected:
                    composer_data["name"] = corrected
                    composer_file.write_text(json_utils.dumps(composer_data, indent=2))
                    if self.logger:
                        self.logger.info(f"Sanitized composer name: {original_name!r} -> {corrected!r}")
            except Exception as e:
                if self.logger:
                    self.logger.warning(f"Error sanitizing composer.json: {e}")
        # composer install
        result = await self.run_command(["composer", "install"], cwd=str(code_path))
        if result.returncode != 0 and self.logger:
            self.logger.warning(f"Composer install failed: {result.stderr}")
        # dev deps (idempotent)
        dev = await self.run_command(
            ["composer", "require", "--dev", "phpstan/phpstan", "laravel/pint", "pestphp/pest"],
            cwd=str(code_path),
        )
        if dev.returncode != 0 and self.logger:
            self.logger.warning(f"Laravel dev deps failed: {dev.stderr}")
        return True

# auto-register
StackRegistry.register(LaravelHandler.name, LaravelHandler)