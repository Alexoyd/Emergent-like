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
        yarn_lock = code_path / "yarn.lock"
        if yarn_lock.exists():
            res = await self.run_command(["yarn", "install"], cwd=str(code_path))
            if res.returncode == 0:
                return True
        npm = await self.run_command(["npm", "install"], cwd=str(code_path))
        return npm.returncode == 0

StackRegistry.register(VueHandler.name, VueHandler)