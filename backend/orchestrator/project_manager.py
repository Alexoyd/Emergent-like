import os
import logging
import asyncio
import shutil
import re
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import subprocess
import tempfile

from .stacks.registry import StackFactory
from . import stacks  # triggers default handler registration
from .utils import json_utils

logger = logging.getLogger(__name__)

class ProjectManager:
    """High-level orchestration, delegating stack duties to handlers."""

    def __init__(self):
        self.projects_base_path = Path(os.getenv("PROJECTS_BASE_PATH", "/app/projects"))
        self.auto_create_structures = os.getenv("AUTO_CREATE_STRUCTURES", "true").lower() == "true"
        self.test_commands: Dict[str, List[str]] = {
            # centralized defaults; handlers still own their defaults
            "laravel": ["vendor/bin/pest", "-q"],
            "react": ["npm", "test", "--", "--watchAll=false"],
            "vue": ["npm", "test", "--", "--watchAll=false"],
            "python": ["pytest", "-q"],
            "node": ["npm", "test", "--", "--watchAll=false"],
                }
        self.projects_base_path.mkdir(parents=True, exist_ok=True)
 
    async def create_project_workspace(self, project_id: str, stack: str, project_name: str = None) -> Dict[str, Any]:
        """Create isolated workspace for a project"""
        try:
            project_path = self.projects_base_path / project_id
            project_path.mkdir(parents=True, exist_ok=True)
            
            # Create directory structure
            directories = {
                "code": project_path / "code",
                "logs": project_path / "logs", 
                "tests": project_path / "tests",
                "patches": project_path / "patches",
                "backups": project_path / "backups",
                "git": project_path / "git"
            }
            
            for name, path in directories.items():
                path.mkdir(parents=True, exist_ok=True)
            
            # Configure file handler specific to this project
            project_logger = logging.getLogger(f"project.{project_id}")
            project_logger.setLevel(logging.INFO)
            
            log_file = directories["logs"] / "run.log"
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(logging.INFO)
            formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
            file_handler.setFormatter(formatter)

            # To avoid duplicate logs, check before adding
            if not any(isinstance(h, logging.FileHandler) and h.baseFilename == str(log_file) 
                    for h in logger.handlers):
                project_logger.addHandler(file_handler)
            
            # Create project metadata
            metadata = {
                "id": project_id,
                "name": project_name or f"Project {project_id[:8]}",
                "stack": stack,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "directories": {name: str(path) for name, path in directories.items()},
                "status": "initialized"
            }
            
            # Save metadata
            metadata_file = project_path / "project.json"
            with open(metadata_file, 'w') as f:
                json_utils.dump(metadata, f, indent=2)
            
            # Auto-create project structure if enabled
            if self.auto_create_structures:
                # 🚀 Laravel projects use official Composer installation flow
                if stack == "laravel":
                    logger.info(f"🚀 Creating full Laravel project via Composer for {project_id}")
                    try:
                        handler = self._new_handler(stack)
                        await handler.create_project_skeleton(directories["code"], project_name)
                        metadata["dependencies_installed"] = True
                        logger.info("✅ Laravel 12 project created successfully")
                    except Exception as e:
                        metadata["dependencies_installed"] = False
                        logger.error(f"❌ Laravel project creation failed: {e}")
                        raise
                else:
                    # Other stacks continue with normal flow
                    await self._create_project_structure(directories["code"], stack, project_name)
                
                    # ✅ Install dependencies automatically after scaffolding (for non-Laravel stacks only)
                    logger.info(f"Auto-installing dependencies for {stack} project {project_id}")
                try:
                    install_success = await self.install_dependencies(str(project_path), stack)
                    if install_success:
                        metadata["dependencies_installed"] = True
                        logger.info(f"Dependencies successfully installed for {stack} project")
                    else:
                        metadata["dependencies_installed"] = False
                        logger.warning(f"Dependencies installation failed for {stack} project")
                except Exception as e:
                    metadata["dependencies_installed"] = False
                    logger.warning(f"Dependencies installation failed for {stack} project: {e}")
            
            logger.info(f"Created workspace for project {project_id} with stack {stack}")
            return {
                "project_id": project_id,
                "project_path": str(project_path),
                "code_path": str(directories["code"]),
                "logs_path": str(directories["logs"]),
                "metadata": metadata
            }
            
        except Exception as e:
            logger.error(f"Error creating project workspace: {e}")
            raise
    
    async def create_project_skeleton(self, project_id: str, stack: str, project_name: Optional[str] = None) -> str:
        """Generic method to scaffold a project (exposed explicitly)."""
        project_path = self.get_project_path(project_id)
        code_path = self.get_code_path(project_id)
        handler = self._new_handler(stack)
        await handler.create_project_skeleton(code_path, project_name)
        
        # Skip redundant dependency installation for Laravel (already done in create_project_skeleton)
        if stack != "laravel":
            logger.info(f"Installing dependencies for {stack} project {project_id}")
            await self.install_dependencies(str(code_path), stack)
        else:
            logger.info("🚀 Laravel dependencies already installed via Composer create-project")
        
        # Create test skeletons for better test coverage
        await self.create_test_skeletons(str(code_path), stack)
        
        # ✅ Phase 1: Auto-setup environment after project creation
        try:
            from .tools import ToolManager
            # Import LLMRouter for auto-setup
            from .llm_router import LLMRouter
            llm_router = LLMRouter()
            tool_manager = ToolManager(llm_router=llm_router)
            setup_success = await tool_manager.auto_setup_environment(str(code_path), stack)
            if setup_success:
                logger.info(f"✅ Environment auto-setup completed for {stack} project")
            else:
                logger.warning("⚠️ Environment auto-setup had issues, but project created")
        except Exception as e:
            logger.warning(f"Environment auto-setup error: {e}")
        
        return str(project_path)
    
    async def install_dependencies(self, project_path: str, stack: str) -> bool:
        """Backward compatible signature; delegates to stack handler."""
        code_path = Path(project_path) / "code"
        handler = self._new_handler(stack)
        return await handler.install_dependencies(code_path)   
    
    async def create_test_skeletons(self, code_path: str, stack: str) -> bool:
        """Create test skeleton files for better test coverage."""
        try:
            code_path_obj = Path(code_path)
            
            if stack == "laravel":
                # Create Laravel test skeletons
                test_dirs = [
                    code_path_obj / "tests" / "Feature",
                    code_path_obj / "tests" / "Unit"
                ]
                for test_dir in test_dirs:
                    test_dir.mkdir(parents=True, exist_ok=True)
                
                # Create basic test files
                (code_path_obj / "tests" / "Feature" / "ExampleTest.php").write_text(
                    '<?php\n\nnamespace Tests\\Feature;\n\nuse Illuminate\\Foundation\\Testing\\RefreshDatabase;\nuse Tests\\TestCase;\n\nclass ExampleTest extends TestCase\n{\n    public function test_the_application_returns_a_successful_response(): void\n    {\n        $response = $this->get(\'/\');\n        $response->assertStatus(200);\n    }\n}\n'
                )
                
            elif stack in ["react", "vue", "node"]:
                # Create JavaScript/Node test skeletons
                test_dir = code_path_obj / "tests"
                test_dir.mkdir(parents=True, exist_ok=True)
                
                if stack == "react":
                    (test_dir / "App.test.js").write_text(
                        'import { render, screen } from \'@testing-library/react\';\nimport App from \'../src/App\';\n\ntest(\'renders learn react link\', () => {\n  render(<App />);\n  const linkElement = screen.getByText(/learn react/i);\n  expect(linkElement).toBeInTheDocument();\n});\n'
                    )
                elif stack == "vue":
                    (test_dir / "App.test.js").write_text(
                        'import { mount } from \'@vue/test-utils\';\nimport App from \'../src/App.vue\';\n\ndescribe(\'App.vue\', () => {\n  it(\'renders properly\', () => {\n    const wrapper = mount(App);\n    expect(wrapper.text()).toContain(\'Hello Vue\');\n  });\n});\n'
                    )
                else:  # node
                    (test_dir / "index.test.js").write_text(
                        'const request = require(\'supertest\');\nconst app = require(\'../src/index\');\n\ndescribe(\'GET /\', () => {\n  it(\'should return 200 OK\', async () => {\n    const response = await request(app).get(\'/\');\n    expect(response.status).toBe(200);\n  });\n});\n'
                    )
                    
            elif stack == "python":
                # Create Python test skeletons
                test_dir = code_path_obj / "tests"
                test_dir.mkdir(parents=True, exist_ok=True)
                
                (test_dir / "__init__.py").write_text("")
                (test_dir / "test_main.py").write_text(
                    'import pytest\nfrom src.main import hello_world\n\ndef test_hello_world():\n    """Test the hello_world function."""\n    result = hello_world()\n    assert result == "Hello, World!"\n\ndef test_example():\n    """Example test case."""\n    assert 1 + 1 == 2\n'
                )
                
                # Create a basic main.py if it doesn't exist
                main_file = code_path_obj / "src" / "main.py"
                if not main_file.exists():
                    main_file.write_text(
                        'def hello_world():\n    """Return a greeting message."""\n    return "Hello, World!"\n\nif __name__ == "__main__":\n    print(hello_world())\n'
                    )
            
            logger.info(f"Created test skeletons for {stack} project at {code_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error creating test skeletons: {e}")
            return False
    async def get_project_info(self, project_id: str) -> Optional[Dict[str, Any]]:
        project_path = self.projects_base_path / project_id
        meta = project_path / "project.json"
        if not meta.exists():
            return None
        try:
            return json.loads(meta.read_text())
        except Exception as e:
            logger.error(f"Error reading project metadata: {e}")
            return None

    async def list_projects(self) -> List[Dict[str, Any]]:
        projects: List[Dict[str, Any]] = []
        for d in self.projects_base_path.iterdir():
            if d.is_dir():
                info = await self.get_project_info(d.name)
                if info:
                    projects.append(info)
        return sorted(projects, key=lambda x: x.get("created_at", ""), reverse=True)

    async def delete_project(self, project_id: str) -> bool:
        project_path = self.projects_base_path / project_id
        try:
            if project_path.exists():
                shutil.rmtree(project_path)
                logger.info(f"Deleted project {project_id}")
                return True
            
        except Exception as e:
            logger.error(f"Error deleting project {project_id}: {e}")
            return False

    def get_project_path(self, project_id: str) -> Path:
        return self.projects_base_path / project_id

    def get_code_path(self, project_id: str) -> Path:
        return self.projects_base_path / project_id / "code"

    async def run_tests(self, project_id: str) -> Dict[str, Any]:
        info = await self.get_project_info(project_id)
        if not info:
            return {"error": "project_not_found"}
        stack = info.get("stack")
        handler = self._new_handler(stack)
        # central config wins
        if stack in self.test_commands:
            handler.config.setdefault("test_command", self.test_commands[stack])
        result = await handler.run_tests(self.get_code_path(project_id))
        return {
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }

    # ------------------------------ internals ------------------------------
    async def _create_project_structure(self, code_path: Path, stack: str, project_name: str):
        """Create project structure based on stack"""
        try:
            code_path.mkdir(parents=True, exist_ok=True)
            
            if stack == "laravel":
                # Create basic Laravel structure
                (code_path / "app").mkdir(exist_ok=True)
                (code_path / "app" / "Http").mkdir(exist_ok=True)
                (code_path / "app" / "Http" / "Controllers").mkdir(exist_ok=True)
                (code_path / "routes").mkdir(exist_ok=True)
                (code_path / "database").mkdir(exist_ok=True)
                (code_path / "database" / "migrations").mkdir(exist_ok=True)
                
                # Create basic files
                (code_path / "composer.json").write_text(json_utils.dumps({
                    "name": f"laravel/{project_name.lower().replace(' ', '-')}",
                    "description": f"Laravel project: {project_name}",
                    "require": {
                        "php": "^8.1",
                        "laravel/framework": "^10.0"
                    }
                }, indent=2))
                
            elif stack == "react":
                # Create basic React structure
                (code_path / "src").mkdir(exist_ok=True)
                (code_path / "src" / "components").mkdir(exist_ok=True)
                (code_path / "public").mkdir(exist_ok=True)
                
                # Create basic files
                (code_path / "package.json").write_text(json_utils.dumps({
                    "name": project_name.lower().replace(' ', '-'),
                    "version": "1.0.0",
                    "dependencies": {
                        "react": "^18.0.0",
                        "react-dom": "^18.0.0"
                    }
                }, indent=2))
                
            elif stack == "vue":
                # Create basic Vue structure
                (code_path / "src").mkdir(exist_ok=True)
                (code_path / "src" / "components").mkdir(exist_ok=True)
                (code_path / "public").mkdir(exist_ok=True)
                
                # Create basic files
                (code_path / "package.json").write_text(json_utils.dumps({
                    "name": project_name.lower().replace(' ', '-'),
                    "version": "1.0.0",
                    "dependencies": {
                        "vue": "^3.0.0"
                    }
                }, indent=2))
                
            elif stack == "python":
                # Create basic Python structure
                (code_path / "src").mkdir(exist_ok=True)
                (code_path / "tests").mkdir(exist_ok=True)
                
                # Create basic files
                (code_path / "requirements.txt").write_text("# Python dependencies\n")
                (code_path / "README.md").write_text(f"# {project_name}\n\nPython project created by AI Agent Orchestrator")
                
            elif stack == "node":
                # Create basic Node.js structure
                (code_path / "src").mkdir(exist_ok=True)
                (code_path / "tests").mkdir(exist_ok=True)
                
                # Create basic files
                (code_path / "package.json").write_text(json_utils.dumps({
                    "name": project_name.lower().replace(' ', '-'),
                    "version": "1.0.0",
                    "main": "src/index.js",
                    "dependencies": {}
                }, indent=2))
            
            logger.info(f"Created {stack} project structure at {code_path}")
            
        except Exception as e:
            logger.error(f"Error creating project structure: {e}")
            raise

    def _new_handler(self, stack: str):
        return StackFactory.create(
            stack,
            run_command=self._run_command,
            logger=logger,
            config={},
        )
    
    async def _run_command(self, command: List[str], cwd: Optional[str] = None):
        """Run shell command"""
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            return type('CommandResult', (), {
                'returncode': process.returncode,
                'stdout': stdout.decode('utf-8', errors='ignore'),
                'stderr': stderr.decode('utf-8', errors='ignore')
            })()
            
        except Exception as e:
            logger.error(f"Command execution error: {e}")
            raise
