# stacks/vue_handler.py
from __future__ import annotations
from pathlib import Path
from typing import Optional, List

from .base_handler import StackHandler
from .registry import StackRegistry

class VueHandler(StackHandler):
    name = "vue"
    default_test_command: List[str] = ["npm", "test", "--", "--watchAll=false"]

    async def create_project_skeleton(self, code_path: Path, project_name: Optional[str] = None) -> None:
        dirs = [
            "src/components",
            "src/views",
            "src/router",
            "src/store",
            "public",
            "tests",
        ]
        for d in dirs:
            (code_path / d).mkdir(parents=True, exist_ok=True)
        files = {
            "package.json": f"""{{\n  \"name\": \"{project_name or 'vue-project'}\",\n  \"version\": \"0.1.0\",\n  \"private\": true,\n  \"scripts\": {{\n    \"serve\": \"vue-cli-service serve\",\n    \"build\": \"vue-cli-service build\",\n    \"test\": \"vue-cli-service test:unit\",\n    \"lint\": \"vue-cli-service lint\"\n  }},\n  \"dependencies\": {{\n    \"vue\": \"^3.0.0\",\n    \"vue-router\": \"^4.0.0\"\n  }},\n  \"devDependencies\": {{\n    \"@vue/cli-service\": \"^5.0.0\",\n    \"@vue/test-utils\": \"^2.0.0\",\n    \"jest\": \"^29.0.0\"\n  }}\n}}""",
            "src/App.vue": """<template>\n  <div id=\"app\">\n    <header>\n      <h1>Welcome to Vue.js</h1>\n    </header>\n    <main>\n      <p>This is a Vue.js application.</p>\n    </main>\n  </div>\n</template>\n<script>\nexport default { name: 'App' }\n</script>\n<style>\n#app {\n  font-family: 'Avenir', Helvetica, Arial, sans-serif;\n  text-align: center;\n  color: #2c3e50;\n  margin-top: 60px;\n}\n</style>\n""",
            "src/main.js": """import { createApp } from 'vue'\nimport App from './App.vue'\ncreateApp(App).mount('#app')\n""",
            "public/index.html": f"""<!DOCTYPE html>\n<html lang=\"en\">\n  <head>\n    <meta charset=\"utf-8\">\n    <meta name=\"viewport\" content=\"width=device-width,initial-scale=1.0\">\n    <title>{project_name or 'Vue App'}</title>\n  </head>\n  <body>\n    <noscript>\n      <strong>We're sorry but this app doesn't work properly without JavaScript enabled.</strong>\n    </noscript>\n    <div id=\"app\"></div>\n  </body>\n</html>""",
        }
        for fp, content in files.items():
            p = code_path / fp
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)
        if self.logger:
            self.logger.info(f"Created Vue structure at {code_path}")

    async def install_dependencies(self, code_path: Path) -> bool:
        """Install Vue.js dependencies with enhanced dev tools setup"""
        success = True
        
        # 1. Install base dependencies (yarn preferred, npm fallback)
        yarn_lock = code_path / "yarn.lock"
        if yarn_lock.exists():
            if self.logger:
                self.logger.info("Installing Vue dependencies with yarn...")
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
                self.logger.info("Installing Vue dependencies with npm...")
            npm = await self.run_command(["npm", "install"], cwd=str(code_path))
            success = npm.returncode == 0
            package_manager = "npm" if success else None
        
        if not success or not package_manager:
            if self.logger:
                self.logger.error("Failed to install base dependencies")
            return False
        
        # 2. Install essential dev dependencies for testing/linting
        dev_deps = [
            "vitest@^0.34.0",
            "eslint@^8.0.0", 
            "@vue/test-utils@^2.4.0",
            "@vitejs/plugin-vue@^4.0.0",
            "jsdom@^22.0.0"  # Required for vitest browser environment
        ]
        
        if self.logger:
            self.logger.info("Installing Vue dev dependencies (vitest, eslint, test-utils)...")
        
        install_cmd = ["yarn", "add", "-D"] if package_manager == "yarn" else ["npm", "install", "--save-dev"]
        dev_result = await self.run_command(install_cmd + dev_deps, cwd=str(code_path))
        
        if dev_result.returncode != 0:
            if self.logger:
                self.logger.warning(f"Some dev dependencies failed to install: {dev_result.stderr}")
            # Don't fail the whole process for dev deps, but log the issue
        else:
            if self.logger:
                self.logger.info("✅ Vue dev dependencies installed successfully")
        
        # 3. Update package.json scripts if needed
        await self._ensure_vue_test_scripts(code_path)
        
        return success
    
    async def _ensure_vue_test_scripts(self, code_path: Path) -> None:
        """Ensure package.json has proper test and lint scripts"""
        try:
            import json
            package_json_path = code_path / "package.json"
            
            if not package_json_path.exists():
                return
            
            with open(package_json_path, 'r') as f:
                package_data = json.load(f)
            
            # Update scripts for modern Vue.js with Vitest
            scripts = package_data.get('scripts', {})
            scripts.update({
                "test": "vitest run",
                "test:watch": "vitest",
                "test:ui": "vitest --ui",
                "lint": "eslint src/ --ext .js,.vue",
                "lint:fix": "eslint src/ --ext .js,.vue --fix"
            })
            package_data['scripts'] = scripts
            
            # Add vitest config in package.json if not exists
            if 'vitest' not in package_data:
                package_data['vitest'] = {
                    "environment": "jsdom",
                    "testMatch": ["**/src/**/*.{test,spec}.{js,ts,vue}"],
                    "collectCoverage": True,
                    "coverageDirectory": "coverage"
                }
            
            with open(package_json_path, 'w') as f:
                json.dump(package_data, f, indent=2)
            
            if self.logger:
                self.logger.info("Updated Vue package.json with test scripts")
                
        except Exception as e:
            if self.logger:
                self.logger.warning(f"Failed to update Vue test scripts: {e}")

StackRegistry.register(VueHandler.name, VueHandler)