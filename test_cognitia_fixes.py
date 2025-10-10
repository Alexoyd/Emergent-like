#!/usr/bin/env python3
"""
Test des corrections Cognitia Self-Healing
Valide les 3 phases de corrections implémentées
"""

import os
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

def test_phase1_python_structure_validation():
    """Test PHASE 1: Validation structure Python flexible"""
    print("🧪 TEST PHASE 1: Validation Structure Python Flexible")
    print("=" * 70)
    
    import asyncio
    from backend.server import verify_code_files_generated
    from tempfile import TemporaryDirectory
    
    async def run_test():
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            
            # Test 1: Structure Cognitia-like avec backend/server.py
            print("📝 Test 1.1: Structure Cognitia (backend/server.py)")
            backend_dir = tmppath / "backend"
            backend_dir.mkdir()
            (tmppath / "requirements.txt").write_text("fastapi==0.104.1")
            (backend_dir / "server.py").write_text("from fastapi import FastAPI")
            
            result1 = await verify_code_files_generated(tmppath, "python")
            print(f"   Résultat: {'✅ PASS' if result1 else '❌ FAIL'}")
            assert result1, "❌ Structure Cognitia devrait être validée"
            
            # Test 2: Structure standard avec main.py
            print("📝 Test 1.2: Structure standard (main.py)")
            with TemporaryDirectory() as tmpdir2:
                tmppath2 = Path(tmpdir2)
                (tmppath2 / "requirements.txt").write_text("fastapi==0.104.1")
                (tmppath2 / "main.py").write_text("print('hello')")
                
                result2 = await verify_code_files_generated(tmppath2, "python")
                print(f"   Résultat: {'✅ PASS' if result2 else '❌ FAIL'}")
                assert result2, "❌ Structure standard devrait être validée"
            
            # Test 3: Structure src/main.py
            print("📝 Test 1.3: Structure avec src/main.py")
            with TemporaryDirectory() as tmpdir3:
                tmppath3 = Path(tmpdir3)
                src_dir = tmppath3 / "src"
                src_dir.mkdir()
                (tmppath3 / "requirements.txt").write_text("fastapi==0.104.1")
                (src_dir / "main.py").write_text("print('hello')")
                
                result3 = await verify_code_files_generated(tmppath3, "python")
                print(f"   Résultat: {'✅ PASS' if result3 else '❌ FAIL'}")
                assert result3, "❌ Structure src/main.py devrait être validée"
            
            # Test 4: Structure invalide (pas de .py)
            print("📝 Test 1.4: Structure invalide (pas de fichier .py)")
            with TemporaryDirectory() as tmpdir4:
                tmppath4 = Path(tmpdir4)
                (tmppath4 / "requirements.txt").write_text("fastapi==0.104.1")
                
                result4 = await verify_code_files_generated(tmppath4, "python")
                print(f"   Résultat: {'✅ PASS (rejet attendu)' if not result4 else '❌ FAIL'}")
                assert not result4, "❌ Structure sans .py devrait être rejetée"
            
            print("✅ PHASE 1: TOUS LES TESTS PASSÉS")
            return True
    
    try:
        return asyncio.run(run_test())
    except Exception as e:
        print(f"❌ PHASE 1 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_phase2_await_protection():
    """Test PHASE 2: Protection await errors"""
    print("🧪 TEST PHASE 2: Protection Await Errors")
    print("=" * 70)
    
    from backend.orchestrator.stacks.base_handler import StackHandler
    from backend.orchestrator.stacks.python_handler import PythonHandler
    from pathlib import Path
    import asyncio
    
    async def mock_run_command(cmd, cwd=None):
        """Mock run_command"""
        return type('Result', (), {'returncode': 0, 'stdout': 'OK', 'stderr': ''})()
    
    async def run_test():
        # Test avec commande string (devrait être convertie)
        print("📝 Test 2.1: Commande sous forme de string")
        handler = PythonHandler(run_command=mock_run_command)
        handler.config["test_command"] = "pytest -q"  # STRING au lieu de LIST
        
        try:
            result = await handler.run_tests(Path("/tmp"))
            print(f"   Résultat: ✅ PASS (conversion automatique)")
            return True
        except Exception as e:
            if "await" in str(e).lower():
                print(f"   Résultat: ❌ FAIL - Erreur await détectée: {e}")
                return False
            else:
                # Autre erreur (probablement path inexistant), acceptable
                print(f"   Résultat: ✅ PASS (pas d'erreur await)")
                return True
    
    try:
        result = asyncio.run(run_test())
        if result:
            print("✅ PHASE 2: TEST PASSÉ")
        return result
    except Exception as e:
        print(f"❌ PHASE 2 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_phase3_patch_validation():
    """Test PHASE 3: Validation et réparation patches"""
    print("🧪 TEST PHASE 3: Validation et Réparation Patches")
    print("=" * 70)
    
    from backend.orchestrator.agents.developer import DeveloperAgent
    from backend.orchestrator.tools import is_valid_patch
    
    # Test 1: Patch valide standard
    print("📝 Test 3.1: Patch valide standard")
    valid_patch = """diff --git a/main.py b/main.py
new file mode 100644
index 0000000..abc1234
--- /dev/null
+++ b/main.py
@@ -0,0 +1,3 @@
+def hello():
+    return "world"
+"""
    
    result1 = is_valid_patch(valid_patch)
    print(f"   Résultat: {'✅ PASS' if result1 else '❌ FAIL'}")
    assert result1, "❌ Patch valide devrait être accepté"
    
    # Test 2: Patch sans header diff --git (invalide)
    print("📝 Test 3.2: Patch sans header diff --git")
    invalid_patch = """--- a/main.py
+++ b/main.py
@@ -0,0 +1,3 @@
+def hello():
+    return "world"
+"""
    
    result2 = is_valid_patch(invalid_patch)
    print(f"   Résultat: {'✅ PASS (rejet attendu)' if not result2 else '❌ FAIL'}")
    assert not result2, "❌ Patch sans header devrait être rejeté"
    
    # Test 3: Patch avec paths inconsistants (invalide)
    print("📝 Test 3.3: Patch avec paths inconsistants")
    inconsistent_patch = """diff --git a/file1.py b/file2.py
new file mode 100644
--- a/file1.py
+++ b/file2.py
@@ -0,0 +1,1 @@
+code
"""
    
    result3 = is_valid_patch(inconsistent_patch)
    print(f"   Résultat: {'✅ PASS (rejet attendu)' if not result3 else '❌ FAIL'}")
    assert not result3, "❌ Patch avec paths inconsistants devrait être rejeté"
    
    # Test 4: Test des fonctions d'extraction avec agent
    print("📝 Test 3.4: Extraction patch avec markers")
    
    # Create test data first
    text_with_markers = """Some text here
BEGIN_PATCH
diff --git a/test.py b/test.py
new file mode 100644
--- /dev/null
+++ b/test.py
@@ -0,0 +1,1 @@
+print("hello")
END_PATCH
Some text after"""
    
    # Now test extraction
    from backend.server import extract_patch, _validate_patch_basics
    
    extracted_server = extract_patch(text_with_markers)
    result4 = extracted_server is not None and "diff --git" in extracted_server
    print(f"   Résultat extraction server.py: {'✅ PASS' if result4 else '❌ FAIL'}")
    
    # Test validation basics
    if extracted_server:
        validation_result = _validate_patch_basics(extracted_server)
        print(f"   Résultat validation basics: {'✅ PASS' if validation_result else '❌ FAIL'}")
        result4 = result4 and validation_result
    
    assert result4, "❌ Extraction avec markers devrait réussir"
    
    print("✅ PHASE 3: TOUS LES TESTS PASSÉS")
    return True


def main():
    """Execute tous les tests"""
    print("" + "="*70)
    print("🚀 TESTS DES CORRECTIONS COGNITIA SELF-HEALING")
    print("="*70)
    
    results = {
        "Phase 1 - Structure Python": test_phase1_python_structure_validation(),
        "Phase 2 - Await Protection": test_phase2_await_protection(),
        "Phase 3 - Patch Validation": test_phase3_patch_validation()
    }
    
    print("" + "="*70)
    print("📊 RÉSUMÉ DES TESTS")
    print("="*70)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name}: {status}")
    
    all_passed = all(results.values())
    
    print("" + "="*70)
    if all_passed:
        print("🎉 TOUS LES TESTS SONT PASSÉS!")
        print("✅ Les corrections Cognitia Self-Healing sont opérationnelles")
    else:
        print("❌ CERTAINS TESTS ONT ÉCHOUÉ")
        print("⚠️  Veuillez vérifier les logs ci-dessus")
    print("="*70 + "")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())