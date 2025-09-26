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
"package.json": f"""{{\n \"name\": \"{project_name or 'react-project'}\",\n \"version\": \"0.1.0\",\n \"private\": true,\n \"dependencies\": {{\n \"react\": \"^18.0.0\",\n \"react-dom\": \"^18.0.0\",\n \"react-scripts\": \"5.0.1\"\n }},\n \"scripts\": {{\n \"start\": \"react-scripts start\",\n \"build\": \"react-scripts build\",\n \"test\": \"react-scripts test\",\n \"eject\": \"react-scripts eject\",\n \"lint\": \"eslint src/\"\n }},\n \"devDependencies\": {{\n \"@testing-library/jest-dom\": \"^5.0.0\",\n \"@testing-library/react\": \"^13.0.0\",\n \"@testing-library/user-event\": \"^13.0.0\",\n \"eslint\": \"^8.0.0\"\n }}\n}}""",
"src/App.js": """import React from 'react';\nimport './App.css';\n\nfunction App() {\n return (\n <div className=\"App\">\n <header className=\"App-header\">\n <h1>Welcome to React</h1>\n <p>\n Edit <code>src/App.js</code> and save to reload.\n </p>\n </header>\n </div>\n );\n}\nexport default App;\n""",
"src/index.js": """import React from 'react';\nimport ReactDOM from 'react-dom/client';\nimport './index.css';\nimport App from './App';\n\nconst root = ReactDOM.createRoot(document.getElementById('root'));\nroot.render(\n <React.StrictMode>\n <App />\n </React.StrictMode>\n);\n""",
"public/index.html": f"""<!DOCTYPE html>\n<html lang=\"en\">\n <head>\n <meta charset=\"utf-8\" />\n <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />\n <title>{project_name or 'React App'}</title>\n </head>\n <body>\n <noscript>You need to enable JavaScript to run this app.</noscript>\n <div id=\"root\"></div>\n </body>\n</html>""",
}
for fp, content in files.items():
p = code_path / fp
p.parent.mkdir(parents=True, exist_ok=True)
p.write_text(content)
if self.logger:
self.logger.info(f"Created React structure at {code_path}")


async def install_dependencies(self, code_path: Path) -> bool:
yarn_lock = code_path / "yarn.lock"
if yarn_lock.exists():
res = await self.run_command(["yarn", "install"], cwd=str(code_path))
if res.returncode == 0:
return True
npm = await self.run_command(["npm", "install"], cwd=str(code_path))
return npm.returncode == 0


StackRegistry.register(ReactHandler.name, ReactHandler)