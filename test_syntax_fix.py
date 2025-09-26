"""
Test de syntaxe après correction des imports.
"""

import ast
import sys
from pathlib import Path

def test_syntax():
    """Test que server.py compile correctement."""
    try:
        server_path = Path(__file__).parent / "backend" / "server.py"
        with open(server_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Tenter de parser le code
        ast.parse(content)
        print("✓ server.py compile correctement")
        return True
        
    except SyntaxError as e:
        print(f"✗ Erreur de syntaxe dans server.py: {e}")
        print(f"  Ligne {e.lineno}: {e.text}")
        return False
    except Exception as e:
        print(f"✗ Erreur lors du test: {e}")
        return False

def test_imports():
    """Test que les imports sont corrects."""
    try:
        server_path = Path(__file__).parent / "backend" / "server.py"
        with open(server_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Vérifier les imports spécifiques
        required_imports = [
            "from backend.orchestrator.plan_parser import PlanParser",
            "from backend.orchestrator.plan_parser import Step as PlanStep",
            "from backend.orchestrator.agents import PlannerAgent, DeveloperAgent, ReviewerAgent"
        ]
        
        for import_line in required_imports:
            if import_line in content:
                print(f"✓ Import trouvé: {import_line}")
            else:
                print(f"✗ Import manquant: {import_line}")
                return False
        
        return True
        
    except Exception as e:
        print(f"✗ Erreur lors du test des imports: {e}")
        return False

def test_plan_parser_usage():
    """Test que PlanParser est utilisé correctement."""
    try:
        server_path = Path(__file__).parent / "backend" / "server.py"
        with open(server_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Vérifier que plan_parser est initialisé
        if "plan_parser = PlanParser()" in content:
            print("✓ PlanParser initialisé correctement")
        else:
            print("✗ PlanParser non initialisé")
            return False
        
        # Vérifier que PlanStep est utilisé
        if "step: PlanStep," in content:
            print("✓ PlanStep utilisé dans les signatures")
        else:
            print("✗ PlanStep non utilisé dans les signatures")
            return False
        
        # Vérifier que PlanStep est utilisé pour créer des instances
        if "PlanStep(**step_data)" in content:
            print("✓ PlanStep utilisé pour créer des instances")
        else:
            print("✗ PlanStep non utilisé pour créer des instances")
            return False
        
        return True
        
    except Exception as e:
        print(f"✗ Erreur lors du test d'usage: {e}")
        return False

def main():
    """Exécuter tous les tests."""
    print("=== Test de correction des imports ===\n")
    
    tests = [
        ("Syntaxe Python", test_syntax),
        ("Imports corrects", test_imports),
        ("Usage PlanParser", test_plan_parser_usage)
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n--- {test_name} ---")
        result = test_func()
        results.append((test_name, result))
    
    print("\n=== Résumé ===")
    passed = 0
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {test_name}")
        if result:
            passed += 1
    
    print(f"\nRésultat: {passed}/{len(tests)} tests réussis")
    
    if passed == len(tests):
        print("\n🎉 Tous les tests sont passés !")
        print("Les corrections d'imports sont réussies.")
        return True
    else:
        print(f"\n⚠️  {len(tests) - passed} test(s) ont échoué.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)