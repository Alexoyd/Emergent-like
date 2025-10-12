"""
Tests unitaires pour file_writer.py
Tests des fonctionnalités: clamp EOF, support anchor, idempotence, ordre des opérations
"""

import pytest
import asyncio
from pathlib import Path
import tempfile
import shutil

# Import depuis le module parent
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from orchestrator.file_writer import (
    FileWriter,
    FileWriterError,
    execute_operations,
    _sort_operations_by_priority
)


@pytest.fixture
def temp_project():
    """Crée un projet temporaire pour les tests"""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


class TestFileWriterInsert:
    """Tests pour la fonction insert_text avec clamp EOF, anchor, idempotence"""
    
    @pytest.mark.asyncio
    async def test_insert_basic(self, temp_project):
        """Test insertion basique après ligne 0"""
        # Créer un fichier test
        test_file = temp_project / "test.txt"
        test_file.write_text("line 1\nline 2\nline 3\n")
        
        writer = FileWriter(str(temp_project))
        result = await writer.insert_text("test.txt", 0, "inserted line", "test_project")
        
        assert result["status"] == "inserted"
        assert result["after_line"] == 0
        
        content = test_file.read_text()
        lines = content.splitlines()
        assert lines[0] == "inserted line"
        assert lines[1] == "line 1"
    
    @pytest.mark.asyncio
    async def test_insert_eof_anchor(self, temp_project):
        """Test insertion à la fin avec anchor -1"""
        test_file = temp_project / "test.txt"
        test_file.write_text("line 1\nline 2\n")
        
        writer = FileWriter(str(temp_project))
        result = await writer.insert_text("test.txt", -1, "last line", "test_project")
        
        assert result["status"] == "inserted"
        assert result["after_line"] == 2  # EOF = 2 lignes
        
        content = test_file.read_text()
        lines = content.splitlines()
        assert lines[-1] == "last line"
    
    @pytest.mark.asyncio
    async def test_insert_clamp_eof(self, temp_project):
        """Test clamp EOF: ligne > nombre de lignes → clamp à EOF"""
        test_file = temp_project / "test.txt"
        test_file.write_text("line 1\nline 2\n")
        
        writer = FileWriter(str(temp_project))
        # Demander ligne 100 alors qu'il n'y a que 2 lignes
        result = await writer.insert_text("test.txt", 100, "clamped line", "test_project")
        
        assert result["status"] == "inserted"
        assert result["clamped"] == True
        assert result["original_line"] == 100
        assert result["after_line"] == 2  # Clampé à EOF
        
        content = test_file.read_text()
        lines = content.splitlines()
        assert lines[-1] == "clamped line"
    
    @pytest.mark.asyncio
    async def test_insert_idempotence(self, temp_project):
        """Test idempotence: ne pas insérer si contenu existe déjà"""
        test_file = temp_project / "test.txt"
        test_file.write_text("line 1\nduplicate\nline 3\n")
        
        writer = FileWriter(str(temp_project))
        # Tenter d'insérer "duplicate" après ligne 0
        result = await writer.insert_text("test.txt", 0, "duplicate", "test_project")
        
        assert result["status"] == "skipped"
        assert result["reason"] == "content_already_exists"
        
        # Vérifier que le fichier n'a pas changé
        content = test_file.read_text()
        lines = content.splitlines()
        assert lines.count("duplicate") == 1  # Toujours une seule occurrence
    
    @pytest.mark.asyncio
    async def test_insert_negative_invalid(self, temp_project):
        """Test: ligne négative (autre que -1) doit échouer"""
        test_file = temp_project / "test.txt"
        test_file.write_text("line 1\n")
        
        writer = FileWriter(str(temp_project))
        
        with pytest.raises(FileWriterError) as exc_info:
            await writer.insert_text("test.txt", -5, "invalid", "test_project")
        
        assert "Invalid line number" in str(exc_info.value)


class TestOperationsSorting:
    """Tests pour le tri des opérations par priorité"""
    
    def test_sort_create_before_insert(self):
        """Test: create doit venir avant insert"""
        operations = [
            {"type": "insert", "path": "test.txt", "after_line": 0, "content": "insert"},
            {"type": "create", "path": "test.txt", "content": "create"},
        ]
        
        sorted_ops = _sort_operations_by_priority(operations)
        
        assert sorted_ops[0]["type"] == "create"
        assert sorted_ops[1]["type"] == "insert"
    
    def test_sort_delete_last(self):
        """Test: delete doit venir en dernier"""
        operations = [
            {"type": "delete", "path": "old.txt"},
            {"type": "create", "path": "new.txt", "content": "new"},
            {"type": "update", "path": "existing.txt", "content": "updated"},
        ]
        
        sorted_ops = _sort_operations_by_priority(operations)
        
        assert sorted_ops[0]["type"] == "create"
        assert sorted_ops[1]["type"] == "update"
        assert sorted_ops[2]["type"] == "delete"
    
    def test_sort_preserves_relative_order(self):
        """Test: préserver l'ordre relatif entre opérations du même type"""
        operations = [
            {"type": "create", "path": "file3.txt", "content": "3"},
            {"type": "create", "path": "file1.txt", "content": "1"},
            {"type": "create", "path": "file2.txt", "content": "2"},
        ]
        
        sorted_ops = _sort_operations_by_priority(operations)
        
        # L'ordre relatif doit être préservé
        assert sorted_ops[0]["path"] == "file3.txt"
        assert sorted_ops[1]["path"] == "file1.txt"
        assert sorted_ops[2]["path"] == "file2.txt"
    
    def test_sort_complex_scenario(self):
        """Test: scénario complexe avec tous les types d'opérations"""
        operations = [
            {"type": "rename", "old_path": "old.txt", "new_path": "renamed.txt"},
            {"type": "insert", "path": "file.txt", "after_line": 0, "content": "insert"},
            {"type": "delete", "path": "trash.txt"},
            {"type": "create", "path": "new.txt", "content": "new"},
            {"type": "update", "path": "existing.txt", "content": "updated"},
            {"type": "search_replace", "path": "file.txt", "search": "old", "replace": "new"},
        ]
        
        sorted_ops = _sort_operations_by_priority(operations)
        
        # Ordre attendu: create, update/insert/search_replace, rename, delete
        assert sorted_ops[0]["type"] == "create"
        assert sorted_ops[1]["type"] in ["insert", "update", "search_replace"]
        assert sorted_ops[-2]["type"] == "rename"
        assert sorted_ops[-1]["type"] == "delete"


class TestProtectedPaths:
    """Tests pour la validation des chemins protégés"""
    
    @pytest.mark.asyncio
    async def test_protected_env_file(self, temp_project):
        """Test: .env doit être protégé"""
        writer = FileWriter(str(temp_project))
        
        with pytest.raises(FileWriterError) as exc_info:
            await writer.create_file(".env", "SECRET=123", "test_project")
        
        assert "Protected path not writable" in str(exc_info.value)
        assert ".env" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_protected_git_dir(self, temp_project):
        """Test: .git/ doit être protégé"""
        writer = FileWriter(str(temp_project))
        
        with pytest.raises(FileWriterError) as exc_info:
            await writer.create_file(".git/config", "malicious", "test_project")
        
        assert "Protected path not writable" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_protected_vendor_dir(self, temp_project):
        """Test: vendor/ doit être protégé"""
        writer = FileWriter(str(temp_project))
        
        with pytest.raises(FileWriterError) as exc_info:
            await writer.create_file("vendor/package/file.php", "code", "test_project")
        
        assert "Protected path not writable" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_execute_operations_protected_path_propagates(self, temp_project):
        """Test: execute_operations propage FileWriterError pour chemins protégés"""
        operations = [
            {"type": "create", "path": ".env", "content": "SECRET=123"}
        ]
        
        with pytest.raises(FileWriterError) as exc_info:
            await execute_operations(operations, str(temp_project), "test_project")
        
        assert "Protected path not writable" in str(exc_info.value)


class TestExecuteOperationsIntegration:
    """Tests d'intégration pour execute_operations"""
    
    @pytest.mark.asyncio
    async def test_execute_create_then_insert(self, temp_project):
        """Test: create puis insert dans le bon ordre"""
        operations = [
            {"type": "insert", "path": "new.txt", "after_line": 0, "content": "inserted"},
            {"type": "create", "path": "new.txt", "content": "line 1\n"},
        ]
        
        # Les opérations doivent être triées automatiquement
        results = await execute_operations(operations, str(temp_project), "test_project")
        
        # Vérifier que create a été exécuté en premier
        assert results[0]["status"] in ["created", "inserted"]
        assert all(r["status"] in ["created", "inserted"] for r in results)
        
        # Vérifier le contenu final
        content = (temp_project / "new.txt").read_text()
        assert "line 1" in content
        assert "inserted" in content
    
    @pytest.mark.asyncio
    async def test_execute_mixed_operations(self, temp_project):
        """Test: mélange d'opérations complexes"""
        # Créer un fichier initial
        (temp_project / "existing.txt").write_text("old content\n")
        
        operations = [
            {"type": "update", "path": "existing.txt", "content": "updated\n"},
            {"type": "create", "path": "new.txt", "content": "new file\n"},
            {"type": "insert", "path": "existing.txt", "after_line": 0, "content": "inserted"},
        ]
        
        results = await execute_operations(operations, str(temp_project), "test_project")
        
        # Toutes les opérations doivent réussir
        assert all(r["status"] in ["created", "updated", "inserted"] for r in results)
        assert len(results) == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
