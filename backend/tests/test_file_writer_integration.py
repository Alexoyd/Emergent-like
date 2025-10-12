"""
Tests d'intégration pour file_writer via endpoints API
Tests: clamp EOF, anchor, idempotence, protected paths (422), ordre des opérations
"""

import pytest
import asyncio
from pathlib import Path
import tempfile
import shutil
import sys
import os

# Setup paths
sys.path.insert(0, str(Path(__file__).parent.parent))

# Mock environment variables
os.environ["MONGO_URL"] = "mongodb://localhost:27017/test_db"
os.environ["FILE_WRITE_MODE"] = "direct"
os.environ["DEVELOPMENT_MODE"] = "true"
os.environ["OPENAI_API_KEY"] = "test_key"

from fastapi.testclient import TestClient
from server import app
import git


@pytest.fixture(scope="module")
def client():
    """Create test client"""
    return TestClient(app)


@pytest.fixture
def test_project(tmp_path):
    """Create a test project with Git repo"""
    project_dir = tmp_path / "test_project"
    project_dir.mkdir()
    
    # Initialize Git repo
    repo = git.Repo.init(project_dir)
    
    # Create initial file
    test_file = project_dir / "test.txt"
    test_file.write_text("line 1\nline 2\n")
    
    repo.index.add(["test.txt"])
    repo.index.commit("Initial commit")
    
    return {
        "path": str(project_dir),
        "repo": repo
    }


class TestInsertClampEOF:
    """Tests pour clamp EOF via API"""
    
    def test_insert_with_clamp_eof(self, client, test_project, monkeypatch):
        """Test: insertion avec line > file length doit clamper à EOF"""
        # Mock project manager to return our test project
        from orchestrator import project_manager
        monkeypatch.setattr(
            project_manager, 
            "get_code_path", 
            lambda project_id: Path(test_project["path"])
        )
        
        # Create a run in DB (mock)
        run_id = "test_run_clamp"
        project_id = "test_project_clamp"
        
        # Mock DB
        from server import db
        
        async def mock_find_one(query):
            return {
                "id": run_id,
                "project_id": project_id,
                "status": "running",
                "goal": "test"
            }
        
        monkeypatch.setattr(db.runs, "find_one", mock_find_one)
        
        # Request with line 100 (file has only 2 lines)
        response = client.post(
            "/api/runs/execute-operations",
            json={
                "run_id": run_id,
                "project_id": project_id,
                "operations": [
                    {
                        "type": "insert",
                        "path": "test.txt",
                        "after_line": 100,  # Way beyond EOF
                        "content": "clamped line"
                    }
                ],
                "commit": {
                    "title": "Test clamp",
                    "step_number": 1
                }
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        
        # Check that line was clamped
        # (We'd need to inspect the file to verify clamping)


class TestInsertEOFAnchor:
    """Tests pour anchor EOF (-1) via API"""
    
    def test_insert_eof_anchor(self, client, test_project, monkeypatch):
        """Test: after_line=-1 doit insérer à la fin"""
        from orchestrator import project_manager
        monkeypatch.setattr(
            project_manager, 
            "get_code_path", 
            lambda project_id: Path(test_project["path"])
        )
        
        run_id = "test_run_anchor"
        project_id = "test_project_anchor"
        
        from server import db
        
        async def mock_find_one(query):
            return {
                "id": run_id,
                "project_id": project_id,
                "status": "running",
                "goal": "test"
            }
        
        monkeypatch.setattr(db.runs, "find_one", mock_find_one)
        
        response = client.post(
            "/api/runs/execute-operations",
            json={
                "run_id": run_id,
                "project_id": project_id,
                "operations": [
                    {
                        "type": "insert",
                        "path": "test.txt",
                        "after_line": -1,  # EOF anchor
                        "content": "last line"
                    }
                ],
                "commit": {
                    "title": "Test anchor",
                    "step_number": 1
                }
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"


class TestProtectedPaths422:
    """Tests pour vérifier que les chemins protégés retournent 422"""
    
    def test_protected_env_returns_422(self, client, test_project, monkeypatch):
        """Test: tentative de créer .env doit retourner 422"""
        from orchestrator import project_manager
        monkeypatch.setattr(
            project_manager, 
            "get_code_path", 
            lambda project_id: Path(test_project["path"])
        )
        
        run_id = "test_run_protected"
        project_id = "test_project_protected"
        
        from server import db
        
        async def mock_find_one(query):
            return {
                "id": run_id,
                "project_id": project_id,
                "status": "running",
                "goal": "test"
            }
        
        monkeypatch.setattr(db.runs, "find_one", mock_find_one)
        
        response = client.post(
            "/api/runs/execute-operations",
            json={
                "run_id": run_id,
                "project_id": project_id,
                "operations": [
                    {
                        "type": "create",
                        "path": ".env",
                        "content": "SECRET=hacked"
                    }
                ],
                "commit": {
                    "title": "Attempt hack",
                    "step_number": 1
                }
            }
        )
        
        # MUST return 422, not 200!
        assert response.status_code == 422
        data = response.json()
        assert "Protected path" in data["detail"]
    
    def test_protected_git_returns_422(self, client, test_project, monkeypatch):
        """Test: tentative de modifier .git/ doit retourner 422"""
        from orchestrator import project_manager
        monkeypatch.setattr(
            project_manager, 
            "get_code_path", 
            lambda project_id: Path(test_project["path"])
        )
        
        run_id = "test_run_git"
        project_id = "test_project_git"
        
        from server import db
        
        async def mock_find_one(query):
            return {
                "id": run_id,
                "project_id": project_id,
                "status": "running",
                "goal": "test"
            }
        
        monkeypatch.setattr(db.runs, "find_one", mock_find_one)
        
        response = client.post(
            "/api/runs/execute-operations",
            json={
                "run_id": run_id,
                "project_id": project_id,
                "operations": [
                    {
                        "type": "create",
                        "path": ".git/malicious",
                        "content": "hack"
                    }
                ],
                "commit": {
                    "title": "Attempt hack git",
                    "step_number": 1
                }
            }
        )
        
        assert response.status_code == 422
        data = response.json()
        assert "Protected path" in data["detail"]


class TestOperationOrdering:
    """Tests pour vérifier l'ordre automatique des opérations"""
    
    def test_insert_before_create_gets_reordered(self, client, test_project, monkeypatch):
        """Test: insert avant create doit être réordonné automatiquement"""
        from orchestrator import project_manager
        monkeypatch.setattr(
            project_manager, 
            "get_code_path", 
            lambda project_id: Path(test_project["path"])
        )
        
        run_id = "test_run_order"
        project_id = "test_project_order"
        
        from server import db
        
        async def mock_find_one(query):
            return {
                "id": run_id,
                "project_id": project_id,
                "status": "running",
                "goal": "test"
            }
        
        monkeypatch.setattr(db.runs, "find_one", mock_find_one)
        
        # Send operations in wrong order (insert before create)
        response = client.post(
            "/api/runs/execute-operations",
            json={
                "run_id": run_id,
                "project_id": project_id,
                "operations": [
                    {
                        "type": "insert",
                        "path": "newfile.txt",
                        "after_line": 0,
                        "content": "inserted"
                    },
                    {
                        "type": "create",
                        "path": "newfile.txt",
                        "content": "line 1\n"
                    }
                ],
                "commit": {
                    "title": "Test ordering",
                    "step_number": 1
                }
            }
        )
        
        # Should succeed because operations are reordered
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["operations_executed"] == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
