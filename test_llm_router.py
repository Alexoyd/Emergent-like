#!/usr/bin/env python3
"""
Test du LLMRouter avec option ENABLE_ANTHROPIC
"""

import sys
import os
import asyncio
sys.path.append('/app/backend')

# Mock pour éviter les vraies API calls
class MockOpenAI:
    def __init__(self, *args, **kwargs):
        pass

class MockAnthropic:
    def __init__(self, *args, **kwargs):
        pass

# Remplacer les vrais clients
sys.modules['openai'] = type('MockModule', (), {'OpenAI': MockOpenAI})()
sys.modules['anthropic'] = type('MockModule', (), {'Anthropic': MockAnthropic})()

from orchestrator.llm_router import LLMRouter, ModelTier

def test_anthropic_disabled():
    """Test avec Anthropic désactivé"""
    print("🧪 Test LLMRouter avec Anthropic désactivé...")
    
    # Sauvegarder la valeur originale
    original_value = os.environ.get('ENABLE_ANTHROPIC')
    
    try:
        # Désactiver Anthropic
        os.environ['ENABLE_ANTHROPIC'] = 'false'
        
        # Créer le router
        router = LLMRouter()
        
        # Vérifier qu'Anthropic est désactivé
        assert not router.anthropic_enabled, "Anthropic devrait être désactivé"
        assert router.anthropic_client is None, "Le client Anthropic ne devrait pas être initialisé"
        print("✅ Anthropic correctement désactivé")
        
        # Tester le path d'escalation
        escalation_path = router._get_escalation_path(ModelTier.LOCAL)
        
        # Anthropic (PREMIUM) ne devrait pas être dans le path
        assert ModelTier.PREMIUM not in escalation_path, "PREMIUM (Anthropic) ne devrait pas être dans le path"
        print("✅ Path d'escalation sans Anthropic")
        
        print("🎉 Test Anthropic désactivé réussi!")
        
    finally:
        # Restaurer la valeur originale
        if original_value is not None:
            os.environ['ENABLE_ANTHROPIC'] = original_value
        else:
            os.environ.pop('ENABLE_ANTHROPIC', None)

def test_anthropic_enabled():
    """Test avec Anthropic activé"""
    print("\
🧪 Test LLMRouter avec Anthropic activé...")
    
    # Sauvegarder la valeur originale
    original_value = os.environ.get('ENABLE_ANTHROPIC')
    
    try:
        # Activer Anthropic
        os.environ['ENABLE_ANTHROPIC'] = 'true'
        
        # Créer le router
        router = LLMRouter()
        
        # Vérifier qu'Anthropic est activé
        assert router.anthropic_enabled, "Anthropic devrait être activé"
        print("✅ Anthropic correctement activé")
        
        print("🎉 Test Anthropic activé réussi!")
        
    finally:
        # Restaurer la valeur originale
        if original_value is not None:
            os.environ['ENABLE_ANTHROPIC'] = original_value
        else:
            os.environ.pop('ENABLE_ANTHROPIC', None)

def test_env_file_parsing():
    """Test que le fichier .env est correctement parsé"""
    print("\
🧪 Test parsing du fichier .env...")
    
    env_file = "/app/backend/.env"
    
    with open(env_file, 'r') as f:
        content = f.read()
    
    # Vérifier les nouvelles variables
    expected_vars = [
        "ENABLE_ANTHROPIC=true",
        "MAX_LOCAL_RETRIES=3",
        "MAX_ESCALATION_RETRIES=2"
    ]
    
    for var in expected_vars:
        assert var in content, f"Variable {var} devrait être dans .env"
        print(f"✅ {var} trouvé dans .env")
    
    print("🎉 Fichier .env correctement configuré!")

if __name__ == "__main__":
    test_anthropic_disabled()
    test_anthropic_enabled()
    test_env_file_parsing()
    print("\
🎯 Tous les tests LLMRouter sont passés!")
