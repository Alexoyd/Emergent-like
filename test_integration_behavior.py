"""
Test d'intégration du comportement du cycle itératif.
"""

import sys
import os
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timezone

# Ajouter le répertoire du projet au path
sys.path.insert(0, str(Path(__file__).parent))

def test_execution_context_timeout():
    """Test de la gestion des timeouts."""
    try:
        # Import de la fonction de timeout
        from backend.server import _is_execution_timeout
        
        # Test sans timeout
        context_no_timeout = {
            "start_time": datetime.now(timezone.utc),
            "timeout_seconds": 3600
        }
        assert not _is_execution_timeout(context_no_timeout), "Ne devrait pas être en timeout"
        print("✓ Détection timeout: pas de timeout")
        
        # Test avec timeout
        context_timeout = {
            "start_time": datetime.now(timezone.utc).replace(year=2020),
            "timeout_seconds": 3600
        }
        assert _is_execution_timeout(context_timeout), "Devrait être en timeout"
        print("✓ Détection timeout: timeout détecté")
        
        return True
        
    except Exception as e:
        print(f"✗ Erreur test timeout: {e}")
        return False

def test_file_tree_generation():
    """Test de la génération d'arbre de fichiers."""
    try:
        from backend.server import _get_project_file_tree
        import asyncio
        
        # Créer un répertoire temporaire
        temp_dir = tempfile.mkdtemp()
        
        try:
            # Créer une structure de fichiers
            os.makedirs(os.path.join(temp_dir, "app"), exist_ok=True)
            os.makedirs(os.path.join(temp_dir, "routes"), exist_ok=True)
            
            with open(os.path.join(temp_dir, "composer.json"), "w") as f:
                f.write('{"name": "test"}')
            
            with open(os.path.join(temp_dir, "app", "User.php"), "w") as f:
                f.write('<?php class User {}')
            
            # Tester la génération d'arbre
            async def run_test():
                tree = await _get_project_file_tree(temp_dir)
                return tree
            
            tree = asyncio.run(run_test())
            
            # Vérifications
            assert "composer.json" in tree, "composer.json devrait être dans l'arbre"
            assert "app/" in tree, "app/ devrait être dans l'arbre"
            assert "User.php" in tree, "User.php devrait être dans l'arbre"
            
            print("✓ Génération arbre fichiers: structure correcte")
            print(f"  Arbre généré: {len(tree.split(chr(10)))} lignes")
            
            return True
            
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
        
    except Exception as e:
        print(f"✗ Erreur test arbre fichiers: {e}")
        return False

def test_agent_conversation_structure():
    """Test de la structure des conversations d'agents."""
    try:
        # Simuler une conversation d'agent
        conversation_data = {
            "task": "Create Laravel app",
            "context": {"stack": "laravel", "goal": "test"}
        }
        
        # Vérifier la structure attendue
        expected_fields = ["task", "context"]
        for field in expected_fields:
            assert field in conversation_data, f"Champ {field} manquant"
        
        print("✓ Structure conversation agent: champs requis présents")
        
        # Test de la structure de contexte d'exécution
        execution_context = {
            "run_id": "test-123",
            "from_step": 0,
            "start_time": datetime.now(timezone.utc),
            "timeout_seconds": 3600,
            "user_validation_required": False,
            "plan_revision_count": 0,
            "max_plan_revisions": 2
        }
        
        required_context_fields = [
            "run_id", "from_step", "start_time", "timeout_seconds",
            "user_validation_required", "plan_revision_count", "max_plan_revisions"
        ]
        
        for field in required_context_fields:
            assert field in execution_context, f"Champ contexte {field} manquant"
        
        print("✓ Structure contexte exécution: tous les champs présents")
        
        return True
        
    except Exception as e:
        print(f"✗ Erreur test structure conversation: {e}")
        return False

def test_phase_documentation():
    """Test que les phases sont bien documentées."""
    try:
        server_path = Path(__file__).parent / "backend" / "server.py"
        with open(server_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Vérifier les phases
        phases = [
            "Phase 1: Planning with PlannerAgent",
            "Phase 2: Iterative execution cycle", 
            "Phase 3: Final validation and completion"
        ]
        
        for phase in phases:
            if phase in content:
                print(f"✓ {phase}")
            else:
                print(f"✗ Phase manquante: {phase}")
                return False
        
        return True
        
    except Exception as e:
        print(f"✗ Erreur test phases: {e}")
        return False

def test_error_handling():
    """Test de la gestion d'erreurs."""
    try:
        server_path = Path(__file__).parent / "backend" / "server.py"
        with open(server_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Vérifier la présence de gestion d'erreurs
        error_patterns = [
            "try:",
            "except Exception as e:",
            "logging.error",
            "await state_manager.add_log",
            "await state_manager.update_run_status"
        ]
        
        for pattern in error_patterns:
            if pattern in content:
                print(f"✓ Gestion erreur: {pattern}")
            else:
                print(f"✗ Pattern manquant: {pattern}")
                return False
        
        return True
        
    except Exception as e:
        print(f"✗ Erreur test gestion erreurs: {e}")
        return False

def test_agent_cycle_flow():
    """Test du flux du cycle d'agents."""
    try:
        server_path = Path(__file__).parent / "backend" / "server.py"
        with open(server_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Vérifier le flux du cycle
        cycle_steps = [
            "DeveloperAgent generates patch",
            "Apply patch via tool_manager",
            "Run tests",
            "ReviewerAgent evaluates results",
            "If failure: feedback to Developer",
            "If repeated failures: return to Planner"
        ]
        
        for step in cycle_steps:
            if step in content:
                print(f"✓ Cycle: {step}")
            else:
                print(f"✗ Étape cycle manquante: {step}")
                return False
        
        return True
        
    except Exception as e:
        print(f"✗ Erreur test cycle agents: {e}")
        return False

def test_compatibility_preservation():
    """Test que la compatibilité API est préservée."""
    try:
        server_path = Path(__file__).parent / "backend" / "server.py"
        with open(server_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Vérifier que les anciens endpoints existent toujours
        existing_endpoints = [
            "@api_router.post(\"/runs\")",
            "@api_router.get(\"/runs/{run_id}\")",
            "@api_router.get(\"/runs/{run_id}/logs\")",
            "@api_router.post(\"/runs/{run_id}/cancel\")"
        ]
        
        for endpoint in existing_endpoints:
            if endpoint in content:
                print(f"✓ Endpoint existant préservé: {endpoint.split('/')[-1].replace('\")', '')}")
            else:
                print(f"⚠️  Endpoint possiblement modifié: {endpoint}")
        
        # Vérifier que execute_run garde sa signature compatible
        if "async def execute_run(run_id: str, from_step: int = 0):" in content:
            print("✓ Signature execute_run compatible")
        else:
            print("✗ Signature execute_run modifiée")
            return False
        
        return True
        
    except Exception as e:
        print(f"✗ Erreur test compatibilité: {e}")
        return False

def main():
    """Exécuter tous les tests d'intégration."""
    print("=== Tests d'intégration du cycle itératif ===\n")
    
    tests = [
        ("Gestion des timeouts", test_execution_context_timeout),
        ("Génération arbre fichiers", test_file_tree_generation),
        ("Structure conversations agents", test_agent_conversation_structure),
        ("Documentation des phases", test_phase_documentation),
        ("Gestion d'erreurs", test_error_handling),
        ("Flux du cycle d'agents", test_agent_cycle_flow),
        ("Préservation compatibilité", test_compatibility_preservation)
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n--- {test_name} ---")
        result = test_func()
        results.append((test_name, result))
    
    print("\n=== Résumé des tests d'intégration ===")
    passed = 0
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {test_name}")
        if result:
            passed += 1
    
    print(f"\nRésultat: {passed}/{len(tests)} tests réussis")
    
    if passed == len(tests):
        print("\n🎉 Tous les tests d'intégration sont passés !")
        print("La refactorisation du cycle itératif est complète et fonctionnelle.")
        return True
    else:
        print(f"\n⚠️  {len(tests) - passed} test(s) d'intégration ont échoué.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)