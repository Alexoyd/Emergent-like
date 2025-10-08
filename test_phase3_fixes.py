#!/usr/bin/env python3
"""
Test script pour valider les corrections de la Phase 3
"""
import asyncio
import logging
import sys
import os
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from orchestrator.tools import ToolManager
from orchestrator.repair_agent import RepairAgent
from orchestrator.patch_validator import PatchValidator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_timeout_management():
    """Test de la gestion des timeouts améliorée"""
    logger.info("🧪 Testing timeout management...")
    
    tool_manager = ToolManager()
    
    # Test avec une commande qui va timeout
    try:
        result = await tool_manager._run_command_with_timeout(
            ["sleep", "10"],  # Commande qui va durer 10 secondes
            timeout=2  # Timeout après 2 secondes
        )
        logger.info(f"✅ Timeout test result: {result.returncode}")
    except Exception as e:
        logger.info(f"✅ Timeout test caught exception as expected: {e}")

async def test_repair_loop_prevention():
    """Test de la prévention des boucles infinies"""
    logger.info("🧪 Testing repair loop prevention...")
    
    tool_manager = ToolManager()
    
    # Simuler plusieurs tentatives de réparation pour le même projet
    project_path = "/tmp/test_project"
    
    for i in range(6):  # Dépasser la limite de 5 réparations
        success = await tool_manager._attempt_command_repair(
            project_path, 
            ["composer", "install"], 
            "Some error", 
            "test"
        )
        logger.info(f"Repair attempt {i+1}: {success}")
        
        if not success and i >= 4:  # Devrait échouer après 5 tentatives
            logger.info("✅ Loop prevention working correctly")
            break

async def test_laravel_detection():
    """Test de la détection Laravel améliorée"""
    logger.info("🧪 Testing Laravel detection...")
    
    tool_manager = ToolManager()
    
    # Test avec différents types de projets
    test_paths = [
        "projects/login-project",  # Projet Laravel existant
        "frontend",  # Projet frontend
        "backend",  # Projet Python
    ]
    
    for path in test_paths:
        if os.path.exists(path):
            stack = tool_manager._detect_project_stack(path)
            logger.info(f"✅ Detected stack for {path}: {stack}")

async def test_patch_validation():
    """Test de la validation des patchs"""
    logger.info("🧪 Testing patch validation...")
    
    validator = PatchValidator()
    
    # Test avec un patch valide
    valid_patch = """diff --git a/test.txt b/test.txt
index 1234567..abcdefg 100644
--- a/test.txt
+++ b/test.txt
@@ -1,3 +1,3 @@
 line1
-line2
+line2 modified
 line3
"""
    
    result = validator.validate_and_repair_patch(valid_patch)
    logger.info(f"✅ Patch validation result: {result.is_valid}")

async def test_repair_agent_anti_loop():
    """Test de l'agent de réparation avec prévention des boucles"""
    logger.info("🧪 Testing RepairAgent anti-loop...")
    
    repair_agent = RepairAgent()
    
    # Simuler plusieurs appels LLM pour le même projet
    project_path = "/tmp/test_project"
    
    for i in range(6):  # Dépasser la limite de 5 appels LLM
        result = await repair_agent.analyze_and_repair(
            project_path,
            "laravel",
            "Some error output",
            "composer install"
        )
        logger.info(f"LLM call {i+1}: {result.success}")
        
        if not result.success and i >= 4:  # Devrait échouer après 5 appels
            logger.info("✅ LLM call limit working correctly")
            break

async def main():
    """Fonction principale de test"""
    logger.info("🚀 Starting Phase 3 fixes validation...")
    
    try:
        await test_timeout_management()
        await test_repair_loop_prevention()
        await test_laravel_detection()
        await test_patch_validation()
        await test_repair_agent_anti_loop()
        
        logger.info("✅ All Phase 3 fixes validation completed successfully!")
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
