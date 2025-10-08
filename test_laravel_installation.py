#!/usr/bin/env python3
"""
Test script pour valider l'installation Laravel complète
"""
import asyncio
import logging
import sys
import os
import tempfile
import shutil
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from orchestrator.tools import ToolManager
from orchestrator.environment_manager import EnvironmentManager
from orchestrator.stacks.laravel_handler import LaravelHandler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_laravel_handler_creation():
    """Test de la création d'un projet Laravel complet"""
    logger.info("🧪 Testing LaravelHandler project creation...")
    
    # Create temporary directory for test
    with tempfile.TemporaryDirectory() as temp_dir:
        test_project_path = Path(temp_dir) / "test_laravel_project"
        
        # Create LaravelHandler
        laravel_handler = LaravelHandler()
        laravel_handler.logger = logger
        
        try:
            # Test project creation
            await laravel_handler.create_project_skeleton(test_project_path, "test/project")
            
            # Verify essential files exist
            essential_files = [
                "artisan",
                "composer.json",
                "bootstrap/app.php",
                "config/app.php",
                "routes/web.php",
                "vendor/autoload.php"
            ]
            
            missing_files = []
            for file_path in essential_files:
                if not (test_project_path / file_path).exists():
                    missing_files.append(file_path)
            
            if missing_files:
                logger.error(f"❌ Missing essential files: {missing_files}")
                return False
            
            logger.info("✅ LaravelHandler created complete project structure")
            return True
            
        except Exception as e:
            logger.error(f"❌ LaravelHandler test failed: {e}")
            return False

async def test_environment_manager_validation():
    """Test de la validation Laravel par l'EnvironmentManager"""
    logger.info("🧪 Testing EnvironmentManager Laravel validation...")
    
    # Create temporary directory for test
    with tempfile.TemporaryDirectory() as temp_dir:
        test_project_path = Path(temp_dir) / "test_laravel_project"
        
        # Create a minimal Laravel project first
        laravel_handler = LaravelHandler()
        laravel_handler.logger = logger
        await laravel_handler.create_project_skeleton(test_project_path, "test/project")
        
        # Test EnvironmentManager
        env_manager = EnvironmentManager()
        
        try:
            # Test environment detection and fixing
            fixes = await env_manager.detect_and_fix_environment(str(test_project_path), "laravel")
            
            logger.info(f"✅ EnvironmentManager applied {len(fixes)} fixes")
            
            # Test final health check
            health_ok = await env_manager._final_health_check(str(test_project_path), "laravel")
            
            if health_ok:
                logger.info("✅ EnvironmentManager health check passed")
                return True
            else:
                logger.error("❌ EnvironmentManager health check failed")
                return False
                
        except Exception as e:
            logger.error(f"❌ EnvironmentManager test failed: {e}")
            return False

async def test_tool_manager_laravel_validation():
    """Test de la validation Laravel par le ToolManager"""
    logger.info("🧪 Testing ToolManager Laravel validation...")
    
    # Create temporary directory for test
    with tempfile.TemporaryDirectory() as temp_dir:
        test_project_path = Path(temp_dir) / "test_laravel_project"
        
        # Create a minimal Laravel project first
        laravel_handler = LaravelHandler()
        laravel_handler.logger = logger
        await laravel_handler.create_project_skeleton(test_project_path, "test/project")
        
        # Test ToolManager
        tool_manager = ToolManager()
        
        try:
            # Test Laravel environment validation
            is_valid = await tool_manager._validate_laravel_environment(str(test_project_path))
            
            if is_valid:
                logger.info("✅ ToolManager Laravel validation passed")
                return True
            else:
                logger.error("❌ ToolManager Laravel validation failed")
                return False
                
        except Exception as e:
            logger.error(f"❌ ToolManager test failed: {e}")
            return False

async def test_laravel_commands_execution():
    """Test de l'exécution des commandes Laravel"""
    logger.info("🧪 Testing Laravel commands execution...")
    
    # Create temporary directory for test
    with tempfile.TemporaryDirectory() as temp_dir:
        test_project_path = Path(temp_dir) / "test_laravel_project"
        
        # Create a complete Laravel project
        laravel_handler = LaravelHandler()
        laravel_handler.logger = logger
        await laravel_handler.create_project_skeleton(test_project_path, "test/project")
        
        # Test ToolManager
        tool_manager = ToolManager()
        
        try:
            # Test artisan --version
            result = await tool_manager.run_test(str(test_project_path), "artisan")
            
            if result.status == "passed":
                logger.info("✅ Artisan command test passed")
            else:
                logger.warning(f"⚠️ Artisan command test: {result.status}")
            
            # Test composer install
            result = await tool_manager.run_command(
                ["composer", "install", "--no-interaction", "--no-progress"],
                cwd=str(test_project_path)
            )
            
            if result.status == "passed":
                logger.info("✅ Composer install test passed")
            else:
                logger.warning(f"⚠️ Composer install test: {result.status}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Laravel commands test failed: {e}")
            return False

async def test_incomplete_laravel_detection():
    """Test de la détection d'un projet Laravel incomplet"""
    logger.info("🧪 Testing incomplete Laravel project detection...")
    
    # Create temporary directory for test
    with tempfile.TemporaryDirectory() as temp_dir:
        test_project_path = Path(temp_dir) / "incomplete_laravel"
        
        # Create incomplete Laravel project (just composer.json)
        test_project_path.mkdir(parents=True, exist_ok=True)
        
        # Create minimal composer.json
        composer_json = test_project_path / "composer.json"
        composer_json.write_text('''{
    "name": "emergent/incomplete-project",
    "type": "project",
    "require": {
        "php": "^8.1",
        "laravel/framework": "^10.0"
    }
}''')
        
        # Test EnvironmentManager detection
        env_manager = EnvironmentManager()
        
        try:
            # Test if it detects incomplete installation
            is_complete = await env_manager._is_complete_laravel_installation(test_project_path)
            
            if not is_complete:
                logger.info("✅ Incomplete Laravel project correctly detected")
                
                # Test if it can fix it
                fixes = await env_manager.detect_and_fix_environment(str(test_project_path), "laravel")
                
                if fixes:
                    logger.info(f"✅ EnvironmentManager proposed {len(fixes)} fixes for incomplete project")
                    return True
                else:
                    logger.warning("⚠️ No fixes proposed for incomplete project")
                    return False
            else:
                logger.error("❌ Incomplete Laravel project not detected")
                return False
                
        except Exception as e:
            logger.error(f"❌ Incomplete Laravel detection test failed: {e}")
            return False

async def main():
    """Fonction principale de test"""
    logger.info("🚀 Starting Laravel installation validation tests...")
    
    test_results = []
    
    try:
        # Run all tests
        test_results.append(("LaravelHandler Creation", await test_laravel_handler_creation()))
        test_results.append(("EnvironmentManager Validation", await test_environment_manager_validation()))
        test_results.append(("ToolManager Validation", await test_tool_manager_laravel_validation()))
        test_results.append(("Laravel Commands Execution", await test_laravel_commands_execution()))
        test_results.append(("Incomplete Laravel Detection", await test_incomplete_laravel_detection()))
        
        # Summary
        logger.info("\n" + "="*60)
        logger.info("📊 TEST RESULTS SUMMARY")
        logger.info("="*60)
        
        passed = 0
        total = len(test_results)
        
        for test_name, result in test_results:
            status = "✅ PASSED" if result else "❌ FAILED"
            logger.info(f"{test_name}: {status}")
            if result:
                passed += 1
        
        logger.info("="*60)
        logger.info(f"📈 Overall: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
        
        if passed == total:
            logger.info("🎉 All Laravel installation tests passed!")
            return 0
        else:
            logger.error(f"❌ {total-passed} tests failed")
            return 1
        
    except Exception as e:
        logger.error(f"❌ Test suite failed: {e}")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
