"""
Script de test rapide pour vérifier les corrections insert
Execute des tests basiques sans pytest pour validation rapide
"""

import asyncio
import sys
from pathlib import Path
import tempfile
import shutil

sys.path.insert(0, str(Path(__file__).parent.parent))

from orchestrator.file_writer import FileWriter, execute_operations, _sort_operations_by_priority


async def test_clamp_eof():
    """Test clamp EOF"""
    print("🧪 Test 1: Clamp EOF...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.txt"
        test_file.write_text("line 1\nline 2\n")
        
        writer = FileWriter(tmpdir)
        result = await writer.insert_text("test.txt", 100, "clamped", "test")
        
        assert result["clamped"] == True, "Should be clamped"
        assert result["original_line"] == 100, "Should track original line"
        assert result["after_line"] == 2, "Should clamp to EOF (2 lines)"
        
        content = test_file.read_text()
        assert "clamped" in content, "Content should contain 'clamped'"
        
        print("✅ Clamp EOF works correctly!")


async def test_eof_anchor():
    """Test EOF anchor (-1)"""
    print("🧪 Test 2: EOF Anchor...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.txt"
        test_file.write_text("line 1\nline 2\n")
        
        writer = FileWriter(tmpdir)
        result = await writer.insert_text("test.txt", -1, "last", "test")
        
        assert result["status"] == "inserted", "Should be inserted"
        
        content = test_file.read_text()
        lines = content.splitlines()
        assert lines[-1] == "last", "Should be last line"
        
        print("✅ EOF anchor (-1) works correctly!")


async def test_idempotence():
    """Test idempotence"""
    print("🧪 Test 3: Idempotence...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.txt"
        test_file.write_text("line 1\nduplicate\nline 3\n")
        
        writer = FileWriter(tmpdir)
        result = await writer.insert_text("test.txt", 0, "duplicate", "test")
        
        assert result["status"] == "skipped", "Should be skipped"
        assert result["reason"] == "content_already_exists", "Should detect duplicate"
        
        content = test_file.read_text()
        assert content.count("duplicate") == 1, "Should still have only 1 duplicate"
        
        print("✅ Idempotence works correctly!")


def test_operation_sorting():
    """Test operation sorting"""
    print("🧪 Test 4: Operation Sorting...")
    
    operations = [
        {"type": "insert", "path": "test.txt"},
        {"type": "delete", "path": "old.txt"},
        {"type": "create", "path": "new.txt"},
        {"type": "update", "path": "existing.txt"},
    ]
    
    sorted_ops = _sort_operations_by_priority(operations)
    
    assert sorted_ops[0]["type"] == "create", "Create should be first"
    assert sorted_ops[-1]["type"] == "delete", "Delete should be last"
    assert sorted_ops[1]["type"] in ["insert", "update"], "Modifications in middle"
    
    print("✅ Operation sorting works correctly!")


async def test_protected_paths():
    """Test protected paths"""
    print("🧪 Test 5: Protected Paths...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        writer = FileWriter(tmpdir)
        
        # Test .env
        try:
            await writer.create_file(".env", "SECRET=123", "test")
            assert False, "Should have raised error"
        except Exception as e:
            assert "Protected path" in str(e), "Should mention protected path"
            print("  ✅ .env protected")
        
        # Test .git/
        try:
            await writer.create_file(".git/config", "malicious", "test")
            assert False, "Should have raised error"
        except Exception as e:
            assert "Protected path" in str(e), "Should mention protected path"
            print("  ✅ .git/ protected")
        
        # Test vendor/
        try:
            await writer.create_file("vendor/package/file.php", "code", "test")
            assert False, "Should have raised error"
        except Exception as e:
            assert "Protected path" in str(e), "Should mention protected path"
            print("  ✅ vendor/ protected")
        
        print("✅ Protected paths work correctly!")


async def test_create_then_insert():
    """Test create then insert (with automatic sorting)"""
    print("🧪 Test 6: Create + Insert (Auto-sorted)...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Send operations in wrong order
        operations = [
            {"type": "insert", "path": "new.txt", "after_line": 0, "content": "inserted"},
            {"type": "create", "path": "new.txt", "content": "line 1\n"},
        ]
        
        results = await execute_operations(operations, tmpdir, "test")
        
        # Both should succeed
        assert len(results) == 2, "Should have 2 results"
        assert all(r["status"] in ["created", "inserted"] for r in results), "All should succeed"
        
        # Check final content
        content = (Path(tmpdir) / "new.txt").read_text()
        assert "line 1" in content, "Should have line 1"
        assert "inserted" in content, "Should have inserted line"
        
        print("✅ Create + Insert with auto-sorting works correctly!")


async def main():
    """Run all quick tests"""
    print("\n" + "=" * 80)
    print("🚀 QUICK TEST: INSERT FIXES & IMPROVEMENTS")
    print("=" * 80 + "\n")
    
    tests = [
        test_clamp_eof,
        test_eof_anchor,
        test_idempotence,
        test_protected_paths,
        test_create_then_insert,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            await test()
            passed += 1
        except Exception as e:
            print(f"❌ Test failed: {e}")
            failed += 1
    
    # Non-async test
    try:
        test_operation_sorting()
        passed += 1
    except Exception as e:
        print(f"❌ Test failed: {e}")
        failed += 1
    
    print("\n" + "=" * 80)
    print(f"📊 RESULTS: {passed} passed, {failed} failed")
    print("=" * 80 + "\n")
    
    if failed == 0:
        print("✅ ALL TESTS PASSED! Insert fixes are working correctly.")
        return 0
    else:
        print("❌ SOME TESTS FAILED. Please review the errors above.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
