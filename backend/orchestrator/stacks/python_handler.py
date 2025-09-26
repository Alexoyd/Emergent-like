# stacks/python_handler.py
from __future__ import annotations
from pathlib import Path
from typing import Optional, List


from .base_handler import StackHandler
from .registry import StackRegistry


class PythonHandler(StackHandler):
name = "python"
default_test_command: List[str] = ["pytest", "-q"]


async def create_project_skeleton(self, code_path: Path, project_name: Optional[str] = None) -> None:
pkg = project_name or "src"
dirs = [pkg, "tests", "docs"]
for d in dirs:
(code_path / d).mkdir(parents=True, exist_ok=True)
files = {
"requirements.txt": """# Core dependencies\nfastapi==0.104.1\nuvicorn==0.24.0\npydantic==2.5.0\n\n# Dev\npytest==7.4.3\nblack==23.12.1\nmypy==1.8.0\nflake8==6.1.0\n""",
"setup.py": f"""from setuptools import setup, find_packages\n\nsetup(\n name='{project_name or 'python-project'}',\n version='0.1.0',\n packages=find_packages(),\n install_requires=['fastapi','uvicorn','pydantic'],\n python_requires='>=3.8',\n)\n""",
f"{pkg}/__init__.py": "",
f"{pkg}/main.py": f"""from fastapi import FastAPI\n\napp = FastAPI(title='{project_name or 'Python Project'}')\n\n@app.get('/')\nasync def root():\n return {{'message': 'Hello World'}}\n\nif __name__ == '__main__':\n import uvicorn\n uvicorn.run(app, host='0.0.0.0', port=8000)\n""",
"tests/__init__.py": "",
"tests/test_main.py": f"""from fastapi.testclient import TestClient\nfrom {pkg}.main import app\n\nclient = TestClient(app)\n\ndef test_read_main():\n r = client.get('/')\n assert r.status_code == 200\n assert r.json() == {{'message': 'Hello World'}}\n""",
}
for fp, content in files.items():
p = code_path / fp
p.parent.mkdir(parents=True, exist_ok=True)
p.write_text(content)
if self.logger:
self.logger.info(f"Created Python structure at {code_path}")


async def install_dependencies(self, code_path: Path) -> bool:
req = code_path / "requirements.txt"
if req.exists():
res = await self.run_command(["pip", "install", "-r", "requirements.txt"], cwd=str(code_path))
return res.returncode == 0
if self.logger:
self.logger.warning("No requirements.txt found for Python project")
return True


StackRegistry.register(PythonHandler.name, PythonHandler)