import os
import logging
import asyncio
import shutil
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import subprocess
import tempfile

logger = logging.getLogger(__name__)

class ProjectManager:
    def __init__(self):
        self.projects_base_path = Path(os.getenv("PROJECTS_BASE_PATH", "/app/projects"))
        self.auto_create_structures = os.getenv("AUTO_CREATE_STRUCTURES", "true").lower() == "true"
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
                json.dump(metadata, f, indent=2)
            
            # Auto-create project structure if enabled
            if self.auto_create_structures:
                await self._create_project_structure(directories["code"], stack, project_name)
            
                # ✅ Install dependencies automatically after scaffolding
                logger.info(f"Auto-installing dependencies for {stack} project {project_id}")
                install_success = await self.install_dependencies(str(project_path), stack)
                if install_success:
                    metadata["dependencies_installed"] = True
                    logger.info(f"Dependencies successfully installed for {stack} project")
                else:
                    metadata["dependencies_installed"] = False
                    logger.warning(f"Dependencies installation failed for {stack} project")
            
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
    
    async def _create_project_structure(self, code_path: Path, stack: str, project_name: str = None):
        """Auto-create project structure based on stack"""
        try:
            if stack == "laravel":
                await self._create_laravel_structure(code_path, project_name)
            elif stack == "react":
                await self._create_react_structure(code_path, project_name)
            elif stack == "vue":
                await self._create_vue_structure(code_path, project_name)
            elif stack == "python":
                await self._create_python_structure(code_path, project_name)
            elif stack == "node":
                await self._create_node_structure(code_path, project_name)
                
        except Exception as e:
            logger.error(f"Error creating {stack} structure: {e}")
            # Don't fail the workspace creation if structure creation fails
    
    async def _create_laravel_structure(self, code_path: Path, project_name: str = None):
        """Create minimal Laravel structure"""
        try:
            # Create basic Laravel directory structure
            directories = [
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
                "public"
            ]
            
            for dir_path in directories:
                (code_path / dir_path).mkdir(parents=True, exist_ok=True)
            
            # Create basic files
            files = {
                "routes/web.php": """<?php

use Illuminate\Support\Facades\Route;

Route::get('/', function () {
    return view('welcome');
});
""",
                "routes/api.php": """<?php

use Illuminate\Http\Request;
use Illuminate\Support\Facades\Route;

Route::middleware('auth:sanctum')->get('/user', function (Request $request) {
    return $request->user();
});
""",
                "composer.json": f"""{{
    "name": "laravel/{project_name or 'project'}",
    "type": "project",
    "description": "The Laravel Framework.",
    "keywords": ["framework", "laravel"],
    "license": "MIT",
    "require": {{
        "php": "^8.1",
        "laravel/framework": "^10.0"
    }},
    "require-dev": {{
        "pestphp/pest": "^2.0",
        "phpstan/phpstan": "^1.0",
        "laravel/pint": "^1.0"
    }},
    "autoload": {{
        "psr-4": {{
            "App\\\\": "app/",
            "Database\\\\Factories\\\\": "database/factories/",
            "Database\\\\Seeders\\\\": "database/seeders/"
        }}
    }},
    "scripts": {{
        "test": "pest",
        "analyse": "phpstan analyse",
        "format": "pint"
    }}
}}""",
                ".env": """APP_NAME=Laravel
APP_ENV=local
APP_KEY=
APP_DEBUG=true
APP_URL=http://localhost

DB_CONNECTION=sqlite
DB_DATABASE=database/database.sqlite
""",
                "phpunit.xml": """<?xml version="1.0" encoding="UTF-8"?>
<phpunit xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:noNamespaceSchemaLocation="./vendor/phpunit/phpunit/phpunit.xsd"
         bootstrap="vendor/autoload.php"
         colors="true">
    <testsuites>
        <testsuite name="Unit">
            <directory suffix="Test.php">./tests/Unit</directory>
        </testsuite>
        <testsuite name="Feature">
            <directory suffix="Test.php">./tests/Feature</directory>
        </testsuite>
    </testsuites>
</phpunit>"""
            }
            
            for file_path, content in files.items():
                full_path = code_path / file_path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                with open(full_path, 'w') as f:
                    f.write(content)
            
            logger.info(f"Created Laravel structure at {code_path}")
            
        except Exception as e:
            logger.error(f"Error creating Laravel structure: {e}")
            raise
    
    async def _create_react_structure(self, code_path: Path, project_name: str = None):
        """Create minimal React structure"""
        try:
            # Create React directory structure
            directories = [
                "src/components",
                "src/hooks",
                "src/utils",
                "src/pages",
                "src/styles",
                "public",
                "tests"
            ]
            
            for dir_path in directories:
                (code_path / dir_path).mkdir(parents=True, exist_ok=True)
            
            # Create basic files
            files = {
                "package.json": f"""{{
  "name": "{project_name or 'react-project'}",
  "version": "0.1.0",
  "private": true,
  "dependencies": {{
    "react": "^18.0.0",
    "react-dom": "^18.0.0",
    "react-scripts": "5.0.1"
  }},
  "scripts": {{
    "start": "react-scripts start",
    "build": "react-scripts build", 
    "test": "react-scripts test",
    "eject": "react-scripts eject",
    "lint": "eslint src/"
  }},
  "devDependencies": {{
    "@testing-library/jest-dom": "^5.0.0",
    "@testing-library/react": "^13.0.0",
    "@testing-library/user-event": "^13.0.0",
    "eslint": "^8.0.0"
  }}
}}""",
                "src/App.js": """import React from 'react';
import './App.css';

function App() {
  return (
    <div className="App">
      <header className="App-header">
        <h1>Welcome to React</h1>
        <p>
          Edit <code>src/App.js</code> and save to reload.
        </p>
      </header>
    </div>
  );
}

export default App;
""",
                "src/index.js": """import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import App from './App';

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
""",
                "public/index.html": f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{project_name or 'React App'}</title>
  </head>
  <body>
    <noscript>You need to enable JavaScript to run this app.</noscript>
    <div id="root"></div>
  </body>
</html>"""
            }
            
            for file_path, content in files.items():
                full_path = code_path / file_path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                with open(full_path, 'w') as f:
                    f.write(content)
            
            logger.info(f"Created React structure at {code_path}")
            
        except Exception as e:
            logger.error(f"Error creating React structure: {e}")
            raise
    
    async def _create_python_structure(self, code_path: Path, project_name: str = None):
        """Create minimal Python structure"""
        try:
            # Create Python directory structure
            directories = [
                f"{project_name or 'src'}",
                "tests",
                "docs"
            ]
            
            for dir_path in directories:
                (code_path / dir_path).mkdir(parents=True, exist_ok=True)
            
            # Create basic files
            files = {
                "requirements.txt": """# Core dependencies
fastapi==0.104.1
uvicorn==0.24.0
pydantic==2.5.0

# Development dependencies  
pytest==7.4.3
black==23.12.1
mypy==1.8.0
flake8==6.1.0
""",
                "setup.py": f"""from setuptools import setup, find_packages

setup(
    name='{project_name or 'python-project'}',
    version='0.1.0',
    packages=find_packages(),
    install_requires=[
        'fastapi',
        'uvicorn',
        'pydantic'
    ],
    python_requires='>=3.8',
)""",
                f"{project_name or 'src'}/__init__.py": "",
                f"{project_name or 'src'}/main.py": """from fastapi import FastAPI

app = FastAPI(title=f'{project_name or 'Python Project'}')

@app.get('/')
async def root():
    return {'message': 'Hello World'}

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8000)
""",
                "tests/__init__.py": "",
                "tests/test_main.py": """import pytest
from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)

def test_read_main():
    response = client.get('/')
    assert response.status_code == 200
    assert response.json() == {'message': 'Hello World'}
"""
            }
            
            for file_path, content in files.items():
                full_path = code_path / file_path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                with open(full_path, 'w') as f:
                    f.write(content)
            
            logger.info(f"Created Python structure at {code_path}")
            
        except Exception as e:
            logger.error(f"Error creating Python structure: {e}")
            raise
    
    async def _create_node_structure(self, code_path: Path, project_name: str = None):
        """Create minimal Node.js structure"""
        try:
            # Create Node directory structure
            directories = [
                "src",
                "tests",
                "docs"
            ]
            
            for dir_path in directories:
                (code_path / dir_path).mkdir(parents=True, exist_ok=True)
            
            # Create basic files
            files = {
                "package.json": f"""{{
  "name": "{project_name or 'node-project'}",
  "version": "1.0.0",
  "description": "",
  "main": "src/index.js",
  "scripts": {{
    "start": "node src/index.js",
    "dev": "nodemon src/index.js",
    "test": "jest",
    "lint": "eslint src/"
  }},
  "dependencies": {{
    "express": "^4.18.0"
  }},
  "devDependencies": {{
    "jest": "^29.0.0",
    "nodemon": "^3.0.0",
    "eslint": "^8.0.0"
  }}
}}""",
                "src/index.js": f"""const express = require('express');
const app = express();
const port = process.env.PORT || 3000;

app.use(express.json());

app.get('/', (req, res) => {{
  res.json({{ message: 'Hello World from {project_name or 'Node.js'}!' }});
}});

app.listen(port, () => {{
  console.log(`Server running on port ${{port}}`);
}});

module.exports = app;
""",
                "tests/index.test.js": """const request = require('supertest');
const app = require('../src/index');

describe('GET /', () => {
  it('should return Hello World message', async () => {
    const response = await request(app).get('/');
    expect(response.status).toBe(200);
    expect(response.body.message).toContain('Hello World');
  });
});
"""
            }
            
            for file_path, content in files.items():
                full_path = code_path / file_path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                with open(full_path, 'w') as f:
                    f.write(content)
            
            logger.info(f"Created Node.js structure at {code_path}")
            
        except Exception as e:
            logger.error(f"Error creating Node.js structure: {e}")
            raise
    
    async def _create_vue_structure(self, code_path: Path, project_name: str = None):
        """Create minimal Vue.js structure"""
        try:
            # Create Vue directory structure
            directories = [
                "src/components",
                "src/views", 
                "src/router",
                "src/store",
                "public",
                "tests"
            ]
            
            for dir_path in directories:
                (code_path / dir_path).mkdir(parents=True, exist_ok=True)
            
            # Create basic files
            files = {
                "package.json": f"""{{
  "name": "{project_name or 'vue-project'}",
  "version": "0.1.0",
  "private": true,
  "scripts": {{
    "serve": "vue-cli-service serve",
    "build": "vue-cli-service build",
    "test": "vue-cli-service test:unit",
    "lint": "vue-cli-service lint"
  }},
  "dependencies": {{
    "vue": "^3.0.0",
    "vue-router": "^4.0.0"
  }},
  "devDependencies": {{
    "@vue/cli-service": "^5.0.0",
    "@vue/test-utils": "^2.0.0",
    "jest": "^29.0.0"
  }}
}}""",
                "src/App.vue": """<template>
  <div id="app">
    <header>
      <h1>Welcome to Vue.js</h1>
    </header>
    <main>
      <p>This is a Vue.js application.</p>
    </main>
  </div>
</template>

<script>
export default {
  name: 'App'
}
</script>

<style>
#app {
  font-family: 'Avenir', Helvetica, Arial, sans-serif;
  text-align: center;
  color: #2c3e50;
  margin-top: 60px;
}
</style>
""",
                "src/main.js": """import { createApp } from 'vue'
import App from './App.vue'

createApp(App).mount('#app')
""",
                "public/index.html": f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1.0">
    <title>{project_name or 'Vue App'}</title>
  </head>
  <body>
    <noscript>
      <strong>We're sorry but this app doesn't work properly without JavaScript enabled.</strong>
    </noscript>
    <div id="app"></div>
  </body>
</html>"""
            }
            
            for file_path, content in files.items():
                full_path = code_path / file_path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                with open(full_path, 'w') as f:
                    f.write(content)
            
            logger.info(f"Created Vue.js structure at {code_path}")
            
        except Exception as e:
            logger.error(f"Error creating Vue.js structure: {e}")
            raise
    
    async def get_project_info(self, project_id: str) -> Optional[Dict[str, Any]]:
        """Get project information"""
        try:
            project_path = self.projects_base_path / project_id
            metadata_file = project_path / "project.json"
            
            if not metadata_file.exists():
                return None
            
            with open(metadata_file, 'r') as f:
                return json.load(f)
                
        except Exception as e:
            logger.error(f"Error getting project info: {e}")
            return None
    
    async def list_projects(self) -> List[Dict[str, Any]]:
        """List all projects"""
        try:
            projects = []
            
            for project_dir in self.projects_base_path.iterdir():
                if project_dir.is_dir():
                    project_info = await self.get_project_info(project_dir.name)
                    if project_info:
                        projects.append(project_info)
            
            return sorted(projects, key=lambda x: x.get('created_at', ''), reverse=True)
            
        except Exception as e:
            logger.error(f"Error listing projects: {e}")
            return []
    
    async def delete_project(self, project_id: str) -> bool:
        """Delete project workspace"""
        try:
            project_path = self.projects_base_path / project_id
            
            if project_path.exists():
                shutil.rmtree(project_path)
                logger.info(f"Deleted project {project_id}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error deleting project {project_id}: {e}")
            return False
    
    def get_project_path(self, project_id: str) -> Path:
        """Get project path"""
        return self.projects_base_path / project_id
    
    def get_code_path(self, project_id: str) -> Path:
        """Get project code path"""
        return self.projects_base_path / project_id / "code"
    
    async def install_dependencies(self, project_path: str, stack: str) -> bool:
        """Install dependencies for the project based on stack"""
        try:
            code_path = Path(project_path) / "code"
            
            if stack == "laravel":
                logger.info(f"Installing Laravel dependencies for {project_path}")
                # Run composer install in the code directory
                result = await self._run_command(["composer", "install"], cwd=str(code_path))
                if result.returncode != 0:
                    logger.warning(f"Composer install failed: {result.stderr}")
                    return False
                    
            elif stack in ["react", "vue", "node"]:
                logger.info(f"Installing {stack} dependencies for {project_path}")
                # Run yarn install in the code directory
                result = await self._run_command(["yarn", "install"], cwd=str(code_path))
                if result.returncode != 0:
                    logger.warning(f"Yarn install failed: {result.stderr}")
                    return False
                    
            elif stack == "python":
                logger.info(f"Installing Python dependencies for {project_path}")
                # Run pip install -r requirements.txt in the code directory
                requirements_file = code_path / "requirements.txt"
                if requirements_file.exists():
                    result = await self._run_command(
                        ["pip", "install", "-r", "requirements.txt"], 
                        cwd=str(code_path)
                    )
                    if result.returncode != 0:
                        logger.warning(f"Pip install failed: {result.stderr}")
                        return False
                else:
                    logger.warning("No requirements.txt found for Python project")
                    
            logger.info(f"Dependencies installed successfully for {stack} project")
            return True
            
        except Exception as e:
            logger.error(f"Error installing dependencies for {stack}: {e}")
            return False
    
    async def _run_command(self, command: List[str], cwd: str = None):
        """Run shell command"""
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            return type(\'CommandResult\', (), {
                \'returncode\': process.returncode,
                \'stdout\': stdout.decode(\'utf-8\', errors=\'ignore\'),
                \'stderr\': stderr.decode(\'utf-8\', errors=\'ignore\')
            })()
            
        except Exception as e:
            logger.error(f"Command execution error: {e}")
            raise
