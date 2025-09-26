"""
Test simple de la refactorisation sans dépendances lourdes.
"""

import sys
import os
from pathlib import Path

# Ajouter le répertoire du projet au path
sys.path.insert(0, str(Path(__file__).parent))

def test_syntax_validation():
    """Test que le code Python compile correctement."""
    try:
        import py_compile
        
        # Tester la compilation du fichier server.py
        server_path = Path(__file__).parent / "backend" / "server.py"
        py_compile.compile(str(server_path), doraise=True)
        print("✓ server.py compile correctement")
        
        return True
        
    except py_compile.PyCompileError as e:
        print(f"✗ Erreur de compilation: {e}")
        return False
    except Exception as e:
        print(f"✗ Erreur: {e}")
        return False

def test_function_signatures():
    """Test que les signatures de fonctions sont correctes."""
    try:
        # Lire le fichier server.py
        server_path = Path(__file__).parent / "backend" / "server.py"
        with open(server_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Vérifier que execute_run existe
        if "async def execute_run(run_id: str, from_step: int = 0):" in content:
            print("✓ execute_run signature correcte")
        else:
            print("✗ execute_run signature incorrecte")
            return False
        
        # Vérifier les nouvelles fonctions auxiliaires
        helper_functions = [
            "_save_agent_conversation",
            "_execute_step_with_agents", 
            "_finalize_execution",
            "_is_execution_timeout",
            "_get_project_file_tree"
        ]
        
        for func in helper_functions:
            if f"async def {func}(" in content or f"def {func}(" in content:
                print(f"✓ {func} existe")
            else:
                print(f"✗ {func} manquante")
                return False
        
        return True
        
    except Exception as e:
        print(f"✗ Erreur lors de la vérification des signatures: {e}")
        return False

def test_api_endpoints():
    """Test que les nouveaux endpoints API sont présents."""
    try:
        server_path = Path(__file__).parent / "backend" / "server.py"
        with open(server_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Vérifier les nouveaux endpoints
        endpoints = [
            "@api_router.get(\"/runs/{run_id}/agent-conversations\")",
            "@api_router.post(\"/runs/{run_id}/validate-plan\")",
            "@api_router.post(\"/runs/{run_id}/validate-step\")",
            "@api_router.post(\"/runs/{run_id}/interrupt\")",
            "@api_router.get(\"/runs/{run_id}/execution-context\")"
        ]
        
        for endpoint in endpoints:
            if endpoint in content:
                print(f"✓ Endpoint {endpoint.split('/')[-1].split('\"')[0]} existe")
            else:
                print(f"✗ Endpoint {endpoint} manquant")
                return False
        
        return True
        
    except Exception as e:
        print(f"✗ Erreur lors de la vérification des endpoints: {e}")
        return False

def test_architecture_documentation():
    """Test que la documentation de l'architecture est présente."""
    try:
        server_path = Path(__file__).parent / "backend" / "server.py"
        with open(server_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Vérifier la documentation de l'architecture
        architecture_keywords = [
            "PlannerAgent generates initial plan",
            "DeveloperAgent generates patch",
            "ReviewerAgent evaluates results",
            "User validation points",
            "Save agent conversations",
            "Handle timeouts and interruptions"
        ]
        
        for keyword in architecture_keywords:
            if keyword in content:
                print(f"✓ Documentation: {keyword}")
            else:
                print(f"✗ Documentation manquante: {keyword}")
                return False
        
        return True
        
    except Exception as e:
        print(f"✗ Erreur lors de la vérification de la documentation: {e}")
        return False

def test_imports():
    """Test que les imports nécessaires sont présents."""
    try:
        server_path = Path(__file__).parent / "backend" / "server.py"
        with open(server_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Vérifier les imports des agents
        required_imports = [
            "from backend.orchestrator.agents import PlannerAgent, DeveloperAgent, ReviewerAgent",
            "from backend.orchestrator.agents.planner import ProjectContext",
            "from backend.orchestrator.agents.reviewer import TestResult as ReviewerTestResult, ReviewDecision",
            "from backend.orchestrator.plan_parser import Step"
        ]
        
        for import_line in required_imports:
            if import_line in content:
                print(f"✓ Import: {import_line.split(' import ')[1] if ' import ' in import_line else import_line}")
            else:
                print(f"✗ Import manquant: {import_line}")
                return False
        
        return True
        
    except Exception as e:
        print(f"✗ Erreur lors de la vérification des imports: {e}")
        return False

def test_agent_initialization():
    """Test que l'initialisation des agents est présente."""
    try:
        server_path = Path(__file__).parent / "backend" / "server.py"
        with open(server_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Vérifier l'initialisation des agents
        agent_inits = [
            "planner_agent = PlannerAgent(llm_router, rag_system)",
            "developer_agent = DeveloperAgent(llm_router, rag_system, tool_manager)",
            "reviewer_agent = ReviewerAgent(llm_router)"
        ]
        
        for init_line in agent_inits:
            if init_line in content:
                print(f"✓ Initialisation: {init_line.split(' = ')[0]}")
            else:
                print(f"✗ Initialisation manquante: {init_line}")
                return False
        
        return True
        
    except Exception as e:
        print(f"✗ Erreur lors de la vérification de l'initialisation: {e}")
        return False

def main():
    """Exécuter tous les tests."""
    print("=== Test de la refactorisation d'execute_run() ===\n")
    
    tests = [
        ("Validation syntaxique", test_syntax_validation),
        ("Signatures de fonctions", test_function_signatures),
        ("Endpoints API", test_api_endpoints),
        ("Documentation architecture", test_architecture_documentation),
        ("Imports", test_imports),
        ("Initialisation agents", test_agent_initialization)
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
        print("\n🎉 Tous les tests sont passés ! La refactorisation est réussie.")
        return True
    else:
        print(f"\n⚠️  {len(tests) - passed} test(s) ont échoué.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)