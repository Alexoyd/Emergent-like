import json
import asyncio
import types
import pytest
from pathlib import Path

from backend.orchestrator.project_manager import sanitize_composer_name, ProjectManager


@pytest.mark.parametrize(
    "input_name, expected",
    [
        ("Laravel/Project", "laravel/project"),  # uppercase letters
        ("My Package", "default/my-package"),    # spaces and uppercase
        ("vendor_name/myPackage", "vendor_name/my-package"),  # underscores and camel case
        ("invalid@@@name", "default/invalid-name"),  # invalid characters, no slash
        ("good-vendor/good_project", "good-vendor/good_project"),  # already valid
        ("", "default/project"),  # empty name
    ],
)
def test_sanitize_composer_name(input_name, expected):
    assert sanitize_composer_name(input_name) == expected


@pytest.mark.asyncio
async def test_install_dependencies_sanitizes_composer(tmp_path, monkeypatch):
    """Ensure that install_dependencies rewrites composer.json with sanitized name."""
    project_path = tmp_path / "myproj"
    code_dir = project_path / "code"
    code_dir.mkdir(parents=True, exist_ok=True)

    # composer.json with invalid name
    composer_data = {
        "name": "Invalid Name",
        "type": "project",
    }
    composer_file = code_dir / "composer.json"
    composer_file.write_text(json.dumps(composer_data))

    pm = ProjectManager()

    # Monkeypatch *run*command to avoid running external commands
    async def dummy_run(command, cwd=None):
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(pm, "_run_command", dummy_run)

    result = await pm.install_dependencies(str(project_path), "laravel")
    assert result is True

    updated_data = json.loads(composer_file.read_text())
    assert updated_data["name"] == sanitize_composer_name("Invalid Name")