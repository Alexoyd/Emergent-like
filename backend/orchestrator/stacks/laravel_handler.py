# stacks/laravel_handler.py
from __future__ import annotations
from pathlib import Path
from typing import Optional, List
import json
import re

from .base_handler import StackHandler
from .registry import StackRegistry
from backend.orchestrator.utils import json_utils

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
        dirs = [
            "app/Http/Controllers",
            "app/Models",
            "app/Http/Requests",
            "app/Http/Middleware",
            "routes",
            "database/migrations",
            "database/seeders",
            "tests/Feature",
            "tests/Unit",
            "config",
            "resources/views",
            "public",
        ]
        for d in dirs:
            (code_path / d).mkdir(parents=True, exist_ok=True)

        files = {
            "routes/web.php": """<?php\n\nuse Illuminate\\Support\\Facades\\Route;\n\nRoute::get('/', function () {\n    return view('welcome');\n});\n""",
            "routes/api.php": """<?php\n\nuse Illuminate\\Http\\Request;\nuse Illuminate\\Support\\Facades\\Route;\n\nRoute::middleware('auth:sanctum')->get('/user', function (Request $request) {\n    return $request->user();\n});\n""",
            "composer.json": f"""{{\n    \"name\": \"laravel/{project_name or 'project'}\",\n    \"type\": \"project\",\n    \"description\": \"The Laravel Framework.\",\n    \"keywords\": [\"framework\", \"laravel\"],\n    \"license\": \"MIT\",\n    \"require\": {{\n        \"php\": \"^8.1\",\n        \"laravel/framework\": \"^10.0\"\n    }},\n    \"require-dev\": {{\n        \"pestphp/pest\": \"^2.0\",\n        \"phpstan/phpstan\": \"^1.0\",\n        \"laravel/pint\": \"^1.0\"\n    }},\n    \"autoload\": {{\n        \"psr-4\": {{\n            \"App\\\\\": \"app/\",\n            \"Database\\\\Factories\\\\\": \"database/factories/\",\n            \"Database\\\\Seeders\\\\\": \"database/seeders/\"\n        }}\n    }},\n    \"scripts\": {{\n        \"test\": \"pest\",\n        \"analyse\": \"phpstan analyse\",\n        \"format\": \"pint\"\n    }}\n}}""",
            ".env": """APP_NAME=Laravel\nAPP_ENV=local\nAPP_KEY=\nAPP_DEBUG=true\nAPP_URL=http://localhost\n\nDB_CONNECTION=sqlite\nDB_DATABASE=database/database.sqlite\n""",
            "phpunit.xml": """<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<phpunit xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\"\n         xsi:noNamespaceSchemaLocation=\"./vendor/phpunit/phpunit/phpunit.xsd\"\n         bootstrap=\"vendor/autoload.php\"\n         colors=\"true\">\n    <testsuites>\n        <testsuite name=\"Unit\">\n            <directory suffix=\"Test.php\">./tests/Unit</directory>\n        </testsuite>\n        <testsuite name=\"Feature\">\n            <directory suffix=\"Test.php\">./tests/Feature</directory>\n        </testsuite>\n    </testsuites>\n</phpunit>""",
        }
        for fp, content in files.items():
            p = code_path / fp
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)
        if self.logger:
            self.logger.info(f"Created Laravel structure at {code_path}")

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