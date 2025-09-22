#!/usr/bin/env python3
"""
Test du système d'installation automatique des dépendances
"""

import sys
import os
import asyncio
sys.path.append('/app/backend')

from orchestrator.project_manager import ProjectManager

async def test_laravel_project_creation():
    """Test la création d'un projet Laravel avec installation des dépendances"""
    print("🧪 Test création projet Laravel avec dépendances...")
    
    # Créer une instance du ProjectManager
    pm = ProjectManager()
    
    # Créer un projet Laravel de test
    project_id = "test-laravel-deps"
    
    try:
        # Supprimer le projet s'il existe déjà
        await pm.delete_project(project_id)
        
        # Créer le workspace (devrait installer les dépendances automatiquement)
        result = await pm.create_project_workspace(
            project_id=project_id,
            stack="laravel", 
            project_name="test-laravel"
        )
        
        print(f"✅ Workspace créé: {result['project_id']}")
        
        # Vérifier que les dépendances ont été tentées d'installation
        project_info = await pm.get_project_info(project_id)
        
        print(f"📊 Métadonnées du projet: {project_info.get('dependencies_installed', 'N/A')}")
        
        # Vérifier que composer.json existe
        code_path = pm.get_code_path(project_id)
        composer_json = code_path / "composer.json"
        
        if composer_json.exists():
            print("✅ composer.json créé correctement")
        else:
            print("❌ composer.json manquant")
        
        # Nettoyer le projet de test
        await pm.delete_project(project_id)
        print("✅ Projet de test nettoyé")
        
        print("🎉 Test création Laravel terminé!")
        
    except Exception as e:
        print(f"❌ Erreur lors du test: {e}")
        # Nettoyer en cas d'erreur
        try:
            await pm.delete_project(project_id)
        except:
            pass

async def test_react_project_creation():
    """Test la création d'un projet React avec installation des dépendances"""
    print("\
🧪 Test création projet React avec dépendances...")
    
    pm = ProjectManager()
    project_id = "test-react-deps"
    
    try:
        await pm.delete_project(project_id)
        
        result = await pm.create_project_workspace(
            project_id=project_id,
            stack="react",
            project_name="test-react"
        )
        
        print(f"✅ Workspace React créé: {result['project_id']}")
        
        # Vérifier package.json
        code_path = pm.get_code_path(project_id)
        package_json = code_path / "package.json"
        
        if package_json.exists():
            print("✅ package.json créé correctement")
        else:
            print("❌ package.json manquant")
            
        await pm.delete_project(project_id)
        print("✅ Projet React de test nettoyé")
        
        print("🎉 Test création React terminé!")
        
    except Exception as e:
        print(f"❌ Erreur lors du test React: {e}")
        try:
            await pm.delete_project(project_id)
        except:
            pass

if __name__ == "__main__":
    asyncio.run(test_laravel_project_creation())
    asyncio.run(test_react_project_creation())
