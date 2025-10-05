# stacks/react_handler.py
from __future__ import annotations
from pathlib import Path
from typing import Optional, List

from .base_handler import StackHandler
from .registry import StackRegistry

class ReactHandler(StackHandler):
    name = "react"
    default_test_command: List[str] = ["npm", "test", "--", "--watchAll=false"]

    async def create_project_skeleton(self, code_path: Path, project_name: Optional[str] = None) -> None:
        dirs = [
            "src/components",
            "src/hooks",
            "src/utils",
            "src/pages",
            "src/styles",
            "public",
            "tests",
        ]
        for d in dirs:
            (code_path / d).mkdir(parents=True, exist_ok=True)
        files = {
            "package.json": f"""{{\n  \"name\": \"{project_name or 'react-project'}\",\n  \"version\": \"0.1.0\",\n  \"private\": true,\n  \"dependencies\": {{\n    \"react\": \"^18.0.0\",\n    \"react-dom\": \"^18.0.0\",\n    \"react-scripts\": \"5.0.1\"\n  }},\n  \"scripts\": {{\n    \"start\": \"react-scripts start\",\n    \"build\": \"react-scripts build\",\n    \"test\": \"react-scripts test\",\n    \"eject\": \"react-scripts eject\",\n    \"lint\": \"eslint src/\"\n  }},\n  \"devDependencies\": {{\n    \"@testing-library/jest-dom\": \"^5.0.0\",\n    \"@testing-library/react\": \"^13.0.0\",\n    \"@testing-library/user-event\": \"^13.0.0\",\n    \"eslint\": \"^8.0.0\"\n  }}\n}}""",
            "src/App.js": """import React from 'react';\nimport './App.css';\n\nfunction App() {\n  return (\n    <div className=\"App\">\n      <header className=\"App-header\">\n        <h1>Welcome to React</h1>\n        <p>\n          Edit <code>src/App.js</code> and save to reload.\n        </p>\n      </header>\n    </div>\n  );\n}\nexport default App;\n""",
            "src/index.js": """import React from 'react';\nimport ReactDOM from 'react-dom/client';\nimport './index.css';\nimport App from './App';\n\nconst root = ReactDOM.createRoot(document.getElementById('root'));\nroot.render(\n  <React.StrictMode>\n    <App />\n  </React.StrictMode>\n);\n""",
            "public/index.html": f"""<!DOCTYPE html>\n<html lang=\"en\">\n  <head>\n    <meta charset=\"utf-8\" />\n    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />\n    <title>{project_name or 'React App'}</title>\n  </head>\n  <body>\n    <noscript>You need to enable JavaScript to run this app.</noscript>\n    <div id=\"root\"></div>\n  </body>\n</html>""",
        }
        for fp, content in files.items():
            p = code_path / fp
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)
        if self.logger:
            self.logger.info(f"Created React structure at {code_path}")

    async def install_dependencies(self, code_path: Path) -> bool:
        """Install React dependencies with enhanced dev tools setup"""
        success = True
        
        # 1. Install base dependencies (yarn preferred, npm fallback)
        yarn_lock = code_path / "yarn.lock"
        if yarn_lock.exists():
            if self.logger:
                self.logger.info("Installing React dependencies with yarn...")
            res = await self.run_command(["yarn", "install"], cwd=str(code_path))
            if res.returncode == 0:
                package_manager = "yarn"
            else:
                if self.logger:
                    self.logger.warning(f"Yarn install failed: {res.stderr}, trying npm...")
                npm = await self.run_command(["npm", "install"], cwd=str(code_path))
                success = npm.returncode == 0
                package_manager = "npm" if success else None
        else:
            if self.logger:
                self.logger.info("Installing React dependencies with npm...")
            npm = await self.run_command(["npm", "install"], cwd=str(code_path))
            success = npm.returncode == 0
            package_manager = "npm" if success else None
        
        if not success or not package_manager:
            if self.logger:
                self.logger.error("Failed to install base dependencies")
            return False
        
        # 2. Install essential dev dependencies for testing/linting
        dev_deps = [
            "@testing-library/jest-dom@^6.0.0",
            "@testing-library/react@^13.0.0", 
            "@testing-library/user-event@^14.0.0",
            "eslint@^8.0.0",
            "eslint-plugin-react@^7.33.0",
            "eslint-plugin-react-hooks@^4.6.0",
            "@vitejs/plugin-react@^4.0.0"
        ]
        
        if self.logger:
            self.logger.info("Installing React dev dependencies (testing-library, eslint)...")
        
        install_cmd = ["yarn", "add", "-D"] if package_manager == "yarn" else ["npm", "install", "--save-dev"]
        dev_result = await self.run_command(install_cmd + dev_deps, cwd=str(code_path))
        
        if dev_result.returncode != 0:
            if self.logger:
                self.logger.warning(f"Some dev dependencies failed to install: {dev_result.stderr}")
            # Don't fail the whole process for dev deps, but log the issue
        else:
            if self.logger:
                self.logger.info("✅ React dev dependencies installed successfully")
        
        # 3. Update package.json scripts and ESLint config if needed
        await self._ensure_react_test_scripts(code_path)
        
        return success
    
    async def _ensure_react_test_scripts(self, code_path: Path) -> None:
        """Ensure package.json has proper test and lint scripts"""
        try:
            import json
            package_json_path = code_path / "package.json"
            
            if not package_json_path.exists():
                return
            
            with open(package_json_path, 'r') as f:
                package_data = json.load(f)
            
            # Update scripts for React testing
            scripts = package_data.get('scripts', {})
            scripts.update({
                "test": "react-scripts test --watchAll=false",
                "test:watch": "react-scripts test",
                "test:coverage": "react-scripts test --coverage --watchAll=false",
                "lint": "eslint src/ --ext .js,.jsx,.ts,.tsx",
                "lint:fix": "eslint src/ --ext .js,.jsx,.ts,.tsx --fix"
            })
            package_data['scripts'] = scripts
            
            # Add jest config for better test setup
            if 'jest' not in package_data:
                package_data['jest'] = {
                    "testEnvironment": "jsdom",
                    "setupFilesAfterEnv": ["<rootDir>/src/setupTests.js"],
                    "collectCoverageFrom": [
                        "src/**/*.{js,jsx,ts,tsx}",
                        "!src/index.js",
                        "!src/reportWebVitals.js"
                    ]
                }
            
            with open(package_json_path, 'w') as f:
                json.dump(package_data, f, indent=2)
            
            # Create setupTests.js if it doesn't exist
            setup_tests_path = code_path / "src" / "setupTests.js"
            if not setup_tests_path.exists():
                setup_tests_path.write_text("import '@testing-library/jest-dom';\n")
            
            if self.logger:
                self.logger.info("Updated React package.json with test scripts and Jest config")
                
        except Exception as e:
            if self.logger:
                self.logger.warning(f"Failed to update React test scripts: {e}")

StackRegistry.register(ReactHandler.name, ReactHandler)