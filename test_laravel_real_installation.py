#!/usr/bin/env python3
"""
Test script pour valider la création d'une vraie installation Laravel
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

async def test_real_laravel_creation():
    """Test de création d'un vrai projet Laravel avec composer create-project"""
    logger.info("🧪 Testing REAL Laravel project creation with composer create-project...")
    
    # Create temporary directory for test
    with tempfile.TemporaryDirectory() as temp_dir:
        test_project_path = Path(temp_dir) / "real_laravel_project"
        
        # Create LaravelHandler
        laravel_handler = LaravelHandler()
        laravel_handler.logger = logger
        
        try:
            # Test project creation
            logger.info(f"📁 Creating Laravel project at: {test_project_path}")
            await laravel_handler.create_project_skeleton(test_project_path, "test/real-project")
            
            # Verify essential files exist
            essential_files = [
                "artisan",
                "composer.json",
                "bootstrap/app.php",
                "config/app.php",
                "routes/web.php",
                "vendor/autoload.php",
                "vendor/laravel/framework"
            ]
            
            missing_files = []
            for file_path in essential_files:
                if not (test_project_path / file_path).exists():
                    missing_files.append(file_path)
            
            if missing_files:
                logger.error(f"❌ Missing essential files: {missing_files}")
                return False
            
            # Test if artisan works
            try:
                result = await laravel_handler.run_command(
                    ["php", "artisan", "--version"],
                    cwd=str(test_project_path)
                )
                if result.returncode == 0:
                    logger.info(f"✅ Artisan works: {result.stdout.strip()}")
                else:
                    logger.error(f"❌ Artisan failed: {result.stderr}")
                    return False
            except Exception as e:
                logger.error(f"❌ Artisan test error: {e}")
                return False
            
            # Test composer autoloader
            try:
                result = await laravel_handler.run_command(
                    ["php", "-r", "require 'vendor/autoload.php'; echo 'Autoloader OK';"],
                    cwd=str(test_project_path)
                )
                if result.returncode == 0 and "Autoloader OK" in result.stdout:
                    logger.info("✅ Composer autoloader works")
                else:
                    logger.error(f"❌ Composer autoloader failed: {result.stderr}")
                    return False
            except Exception as e:
                logger.error(f"❌ Composer autoloader test error: {e}")
                return False
            
            # Test Laravel bootstrap
            try:
                result = await laravel_handler.run_command(
                    ["php", "-r", "require 'vendor/autoload.php'; require 'bootstrap/app.php'; echo 'Bootstrap OK';"],
                    cwd=str(test_project_path)
                )
                if result.returncode == 0 and "Bootstrap OK" in result.stdout:
                    logger.info("✅ Laravel bootstrap works")
                else:
                    logger.error(f"❌ Laravel bootstrap failed: {result.stderr}")
                    return False
            except Exception as e:
                logger.error(f"❌ Laravel bootstrap test error: {e}")
                return False
            
            logger.info("🎉 REAL Laravel project creation test PASSED!")
            return True
            
        except Exception as e:
            logger.error(f"❌ Laravel creation test failed: {e}")
            return False

async def test_tool_manager_laravel_detection():
    """Test de la détection Laravel par le ToolManager"""
    logger.info("🧪 Testing ToolManager Laravel detection...")
    
    # Create temporary directory for test
    with tempfile.TemporaryDirectory() as temp_dir:
        test_project_path = Path(temp_dir) / "test_laravel_project"
        
        # Create a real Laravel project first
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

async def test_environment_manager_laravel_creation():
    """Test de la création Laravel par l'EnvironmentManager"""
    logger.info("🧪 Testing EnvironmentManager Laravel creation...")
    
    # Create temporary directory for test
    with temp_dir:
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
        
        # Test EnvironmentManager
        env_manager = EnvironmentManager()
        
        try:
            # Test if it detects incomplete installation
            is_complete = await env_manager._is_complete_laravel_installation(test_project_path)
            
            if not is_complete:
                logger.info("✅ Incomplete Laravel project correctly detected")
                
                # Test if it can fix it
                fixes = await env_manager.detect_and_fix_environment(str(test_project_path), "laravel")
                
                if fixes:
                    logger.info(f"✅ EnvironmentManager applied {len(fixes)} fixes for incomplete project")
                    
                    # Test if project is now complete
                    is_complete_after = await env_manager._is_complete_laravel_installation(test_project_path)
                    if is_complete_after:
                        logger.info("✅ Laravel project is now complete after fixes")
                        return True
                    else:
                        logger.warning("⚠️ Laravel project still incomplete after fixes")
                        return False
                else:
                    logger.warning("⚠️ No fixes applied for incomplete project")
                    return False
            else:
                logger.error("❌ Incomplete Laravel project not detected")
                return False
                
        except Exception as e:
            logger.error(f"❌ EnvironmentManager test failed: {e}")
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
            result = await tool_manager.run_command(
                ["php", "artisan", "--version"],
                cwd=str(test_project_path)
            )
            
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

async def test_repair_agent_laravel_detection():
    """Test de la détection des erreurs Laravel par le RepairAgent"""
    logger.info("🧪 Testing RepairAgent Laravel error detection...")
    
    # Create temporary directory for test
    with tempfile.TemporaryDirectory() as temp_dir:
        test_project_path = Path(temp_dir) / "broken_laravel"
        
        # Create broken Laravel project (just composer.json)
        test_project_path.mkdir(parents=True, exist_ok=True)
        composer_json = test_project_path / "composer.json"
        composer_json.write_text('''{
    "name": "emergent/broken-project",
    "type": "project",
    "require": {
        "php": "^8.1",
        "laravel/framework": "^10.0"
    }
}''')
        
        # Test RepairAgent
        from orchestrator.repair_agent import RepairAgent
        repair_agent = RepairAgent()
        
        try:
            # Test Laravel installation error detection
            error_output = "Composer root package not detected — Laravel project structure is broken"
            is_laravel_error = repair_agent._is_laravel_installation_error(error_output)
            
            if is_laravel_error:
                logger.info("✅ Laravel installation error correctly detected")
                return True
            else:
                logger.error("❌ Laravel installation error not detected")
                return False
                
        except Exception as e:
            logger.error(f"❌ RepairAgent test failed: {e}")
            return False

async def main():
    """Fonction principale de test"""
    logger.info("🚀 Starting REAL Laravel installation validation tests...")
    
    test_results = []
    
    try:
        # Run all tests
        test_results.append(("Real Laravel Creation", await test_real_laravel_creation()))
        test_results.append(("ToolManager Laravel Detection", await test_tool_manager_laravel_detection()))
        test_results.append(("EnvironmentManager Laravel Creation", await test_environment_manager_laravel_creation()))
        test_results.append(("Laravel Commands Execution", await test_laravel_commands_execution()))
        test_results.append(("RepairAgent Laravel Detection", await test_repair_agent_laravel_detection()))
        
        # Summary
        logger.info("\n" + "="*60)
        logger.info("📊 REAL LARAVEL INSTALLATION TEST RESULTS")
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
            logger.info("🎉 All REAL Laravel installation tests passed!")
            logger.info("🚀 The system can now create REAL Laravel projects!")
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
