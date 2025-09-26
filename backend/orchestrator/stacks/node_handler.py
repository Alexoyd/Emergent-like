# stacks/node_handler.py
from __future__ import annotations
from pathlib import Path
from typing import Optional, List

from .base_handler import StackHandler
from .registry import StackRegistry

class NodeHandler(StackHandler):
    name = "node"
    default_test_command: List[str] = ["npm", "test", "--", "--watchAll=false"]

    async def create_project_skeleton(self, code_path: Path, project_name: Optional[str] = None) -> None:
        dirs = ["src", "tests", "docs"]
        for d in dirs:
            (code_path / d).mkdir(parents=True, exist_ok=True)
        files = {
            "package.json": f"""{{\n  \"name\": \"{project_name or 'node-project'}\",\n  \"version\": \"1.0.0\",\n  \"main\": \"src/index.js\",\n  \"scripts\": {{\n    \"start\": \"node src/index.js\",\n    \"dev\": \"nodemon src/index.js\",\n    \"test\": \"jest\",\n    \"lint\": \"eslint src/\"\n  }},\n  \"dependencies\": {{\n    \"express\": \"^4.18.0\"\n  }},\n  \"devDependencies\": {{\n    \"jest\": \"^29.0.0\",\n    \"nodemon\": \"^3.0.0\",\n    \"eslint\": \"^8.0.0\",\n    \"supertest\": \"^7.0.0\"\n  }}\n}}""",
            "src/index.js": f"""const express = require('express');\nconst app = express();\nconst port = process.env.PORT || 3000;\napp.use(express.json());\napp.get('/', (req, res) => {{ res.json({{ message: 'Hello World from {project_name or 'Node.js'}!' }}); }});\napp.listen(port, () => {{ console.log(`Server running on port ${{port}}`); }});\nmodule.exports = app;\n""",
            "tests/index.test.js": """const request = require('supertest');\nconst app = require('../src/index');\ndescribe('GET /', () => {\n  it('returns Hello World', async () => {\n    const res = await request(app).get('/');\n    expect(res.status).toBe(200);\n    expect(res.body.message).toContain('Hello World');\n  });\n});\n""",
        }
        for fp, content in files.items():
            p = code_path / fp
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)
        if self.logger:
            self.logger.info(f"Created Node structure at {code_path}")

    async def install_dependencies(self, code_path: Path) -> bool:
        yarn_lock = code_path / "yarn.lock"
        if yarn_lock.exists():
            res = await self.run_command(["yarn", "install"], cwd=str(code_path))
            if res.returncode == 0:
                return True
        npm = await self.run_command(["npm", "install"], cwd=str(code_path))
        return npm.returncode == 0

StackRegistry.register(NodeHandler.name, NodeHandler)