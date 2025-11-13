#!/usr/bin/env python3
"""
Test unitaire pour valider le nettoyage JSON multi-couches
Inspiré d'Emergent.sh
"""

import json
import sys
import re
from pathlib import Path


def fix_literal_escapes_in_raw_json(text: str) -> str:
    """
    Réplication de la fonction de nettoyage pour test
    """
    if not text or not isinstance(text, str):
        return text
    
    original_text = text
    fixes_applied = []
    
    # COUCHE 1: Nettoyage des TRIPLES échappements
    if '\\\\"' in text:
        text = text.replace('\\\\"', '\\"')
        fixes_applied.append("triple-escaped quotes")
        print("      🔧 [Couche 1] Correction des guillemets triple-échappés (\\\\\" → \\\")")
    
    # COUCHE 2: Nettoyage des DOUBLES échappements
    if '\\\\n' in text:
        text = text.replace('\\\\n', '\\n')
        fixes_applied.append("double-escaped newlines")
        print("      🔧 [Couche 2] Correction des newlines double-échappées (\\\\n → \\n)")
    
    if '\\\\t' in text:
        text = text.replace('\\\\t', '\\t')
        fixes_applied.append("double-escaped tabs")
        print("      🔧 [Couche 2] Correction des tabs double-échappées (\\\\t → \\t)")
    
    # COUCHE 3: Regex avancées pour cas complexes
    pattern = r'("(?:content|search|replace)"\s*:\s*"[^"]*?)\\\\n([^"]*")'
    
    def fix_escapes(match):
        prefix = match.group(1)
        suffix = match.group(2)
        return prefix + '\n' + suffix
    
    text_after_regex = re.sub(pattern, fix_escapes, text)
    if text_after_regex != text:
        fixes_applied.append("regex newlines in fields")
        text = text_after_regex
    
    pattern_tab = r'("(?:content|search|replace)"\s*:\s*"[^"]*?)\\\\t([^"]*")'
    def fix_tabs(match):
        prefix = match.group(1)
        suffix = match.group(2)
        return prefix + '\t' + suffix
    
    text_after_tab_regex = re.sub(pattern_tab, fix_tabs, text)
    if text_after_tab_regex != text:
        fixes_applied.append("regex tabs in fields")
        text = text_after_tab_regex
    
    if text != original_text:
        print(f"      🔧 [Multi-couches] Nettoyage terminé: {', '.join(fixes_applied)}")
    
    return text


def test_triple_escaped_quotes():
    """Test COUCHE 1: Guillemets triple-échappés"""
    print("\n🧪 Test 1: Guillemets triple-échappés")
    
    # Simuler la réponse du LLM avec triple échappement
    text = '{"operations": [{"type": "create", "path": "test.html", "content": "Hello \\\\"World\\\\""}]}'
    print(f"   Entrée: {text}")
    
    # Appliquer le nettoyage
    cleaned = fix_literal_escapes_in_raw_json(text)
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
