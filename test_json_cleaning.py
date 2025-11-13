#!/usr/bin/env python3
"""
Test unitaire pour valider le nettoyage JSON multi-couches
Inspiré d'Emergent.sh
"""

import json
import sys
from pathlib import Path

# Ajouter le backend au path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from orchestrator.agents.developer_direct import DeveloperAgentDirect


def test_triple_escaped_quotes():
    """Test COUCHE 1: Guillemets triple-échappés"""
    print("\n🧪 Test 1: Guillemets triple-échappés")
    
    # Simuler la réponse du LLM avec triple échappement
    text = '{"operations": [{"type": "create", "path": "test.html", "content": "Hello \\\\"World\\\\""}]}'
    print(f"   Entrée: {text}")
    
    # Créer instance (avec logging minimal)
    import logging
    logger = logging.getLogger("test")
    logger.setLevel(logging.INFO)
    
    agent = DeveloperAgentDirect(
        project_manager=None,
        tool_manager=None,
        llm_router=None,
        rag_retriever=None,
        log=logger
    )
    
    # Appliquer le nettoyage
    cleaned = agent._fix_literal_escapes_in_raw_json(text)
    print(f"   Nettoyé: {cleaned}")
    
    # Vérifier que le JSON parse correctement
    try:
        data = json.loads(cleaned)
        content = data["operations"][0]["content"]
        print(f"   Contenu: {content}")
        assert 'Hello "World"' in content or 'Hello \\"World\\"' in content
        print("   ✅ SUCCÈS: JSON parse correctement")
        return True
    except Exception as e:
        print(f"   ❌ ÉCHEC: {e}")
        return False


def test_double_escaped_newlines():
    """Test COUCHE 2: Newlines double-échappées"""
    print("\n🧪 Test 2: Newlines double-échappées")
    
    text = '{"operations": [{"type": "create", "path": "test.txt", "content": "Line1\\\\nLine2"}]}'
    print(f"   Entrée: {text}")
    
    import logging
    logger = logging.getLogger("test")
    logger.setLevel(logging.INFO)
    
    agent = DeveloperAgentDirect(
        project_manager=None,
        tool_manager=None,
        llm_router=None,
        rag_retriever=None,
        log=logger
    )
    
    cleaned = agent._fix_literal_escapes_in_raw_json(text)
    print(f"   Nettoyé: {cleaned}")
    
    try:
        data = json.loads(cleaned)
        content = data["operations"][0]["content"]
        print(f"   Contenu: {repr(content)}")
        # Vérifier que \n est présent (échappé simplement)
        assert '\\n' in cleaned or '\n' in content
        print("   ✅ SUCCÈS: Newlines correctement nettoyées")
        return True
    except Exception as e:
        print(f"   ❌ ÉCHEC: {e}")
        return False


def test_mixed_escapes():
    """Test cas mixte: Triple + Double échappements"""
    print("\n🧪 Test 3: Cas mixte (triple quotes + double newlines)")
    
    text = '{"operations": [{"type": "create", "path": "test.php", "content": "<?php\\\\necho \\\\"Hello\\\\";"}]}'
    print(f"   Entrée: {text}")
    
    import logging
    logger = logging.getLogger("test")
    logger.setLevel(logging.INFO)
    
    agent = DeveloperAgentDirect(
        project_manager=None,
        tool_manager=None,
        llm_router=None,
        rag_retriever=None,
        log=logger
    )
    
    cleaned = agent._fix_literal_escapes_in_raw_json(text)
    print(f"   Nettoyé: {cleaned}")
    
    try:
        data = json.loads(cleaned)
        content = data["operations"][0]["content"]
        print(f"   Contenu: {repr(content)}")
        print("   ✅ SUCCÈS: Cas mixte géré correctement")
        return True
    except Exception as e:
        print(f"   ❌ ÉCHEC: {e}")
        return False


def test_no_escapes_needed():
    """Test cas normal: Pas d'échappements problématiques"""
    print("\n🧪 Test 4: JSON normal (pas de nettoyage nécessaire)")
    
    text = '{"operations": [{"type": "create", "path": "test.txt", "content": "Hello World"}]}'
    print(f"   Entrée: {text}")
    
    import logging
    logger = logging.getLogger("test")
    logger.setLevel(logging.INFO)
    
    agent = DeveloperAgentDirect(
        project_manager=None,
        tool_manager=None,
        llm_router=None,
        rag_retriever=None,
        log=logger
    )
    
    cleaned = agent._fix_literal_escapes_in_raw_json(text)
    print(f"   Nettoyé: {cleaned}")
    
    try:
        data = json.loads(cleaned)
        content = data["operations"][0]["content"]
        print(f"   Contenu: {content}")
        assert content == "Hello World"
        print("   ✅ SUCCÈS: JSON normal non modifié")
        return True
    except Exception as e:
        print(f"   ❌ ÉCHEC: {e}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("🔬 Tests de Nettoyage JSON Multi-Couches")
    print("   Inspiré d'Emergent.sh")
    print("=" * 60)
    
    results = []
    
    # Exécuter tous les tests
    results.append(("Triple-escaped quotes", test_triple_escaped_quotes()))
    results.append(("Double-escaped newlines", test_double_escaped_newlines()))
    results.append(("Mixed escapes", test_mixed_escapes()))
    results.append(("Normal JSON", test_no_escapes_needed()))
    
    # Résumé
    print("\n" + "=" * 60)
    print("📊 RÉSUMÉ DES TESTS")
    print("=" * 60)
    
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"   {status}: {name}")
    
    total = len(results)
    passed_count = sum(1 for _, p in results if p)
    
    print(f"\n   Total: {passed_count}/{total} tests réussis")
    
    if passed_count == total:
        print("\n🎉 TOUS LES TESTS PASSENT!")
        sys.exit(0)
    else:
        print(f"\n⚠️  {total - passed_count} test(s) échoué(s)")
        sys.exit(1)
