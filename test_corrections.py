#!/usr/bin/env python3
"""
Test script pour vérifier les corrections apportées au système
"""

import sys
import os
sys.path.append('/app/backend')

from orchestrator.tools import is_valid_patch

def test_is_valid_patch():
    """Test la fonction de validation des patches"""
    print("🧪 Test de validation des patches...")
    
    # Test 1: Patch valide
    valid_patch = """diff --git a/test.py b/test.py
index 1234567..abcdefg 100644
--- a/test.py
+++ b/test.py
@@ -1,3 +1,4 @@
 def hello():
+    print("New line added")
     print("Hello World")
     return True"""
    
    assert is_valid_patch(valid_patch), "Le patch valide devrait être accepté"
    print("✅ Patch valide correctement détecté")
    
    # Test 2: Patch invalide - pas de diff --git
    invalid_patch_1 = """--- a/test.py
+++ b/test.py
@@ -1,3 +1,4 @@
 def hello():
+    print("New line added")
     print("Hello World")"""
    
    assert not is_valid_patch(invalid_patch_1), "Le patch sans 'diff --git' devrait être rejeté"
    print("✅ Patch sans 'diff --git' correctement rejeté")
    
    # Test 3: Patch invalide - pas de headers de fichiers
    invalid_patch_2 = """diff --git a/test.py b/test.py
@@ -1,3 +1,4 @@
 def hello():
+    print("New line added")"""
    
    assert not is_valid_patch(invalid_patch_2), "Le patch sans headers de fichiers devrait être rejeté"
    print("✅ Patch sans headers de fichiers correctement rejeté")
    
    # Test 4: Patch vide
    assert not is_valid_patch(""), "Le patch vide devrait être rejeté"
    assert not is_valid_patch(None), "Le patch None devrait être rejeté"
    print("✅ Patches vides correctement rejetés")
    
    print("🎉 Tous les tests de validation des patches sont passés!")

def test_env_anthropic():
    """Test la configuration Anthropic"""
    print("\
🧪 Test de la configuration Anthropic...")
    
    # Vérifier que le fichier .env existe
    env_file = "/app/backend/.env"
    assert os.path.exists(env_file), f"Le fichier {env_file} devrait exister"
    print("✅ Fichier .env créé")
    
    # Vérifier que ENABLE_ANTHROPIC est présent
    with open(env_file, 'r') as f:
        env_content = f.read()
    
    assert "ENABLE_ANTHROPIC" in env_content, "ENABLE_ANTHROPIC devrait être dans .env"
    print("✅ Variable ENABLE_ANTHROPIC présente dans .env")
    
    print("🎉 Configuration Anthropic correctement implémentée!")

if __name__ == "__main__":
    test_is_valid_patch()
    test_env_anthropic()
    print("\
🎯 Toutes les corrections ont été implémentées avec succès!")
