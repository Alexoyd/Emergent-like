#!/usr/bin/env python3
"""
Quick test script to verify PHPStan setup methods work correctly
"""
import asyncio
import sys
import tempfile
from pathlib import Path

# Add backend to path
sys.path.insert(0, '/app/backend')

from orchestrator.tools import ToolManager


async def test_phpstan_config_generation():
    """Test PHPStan config generation"""
    print("🧪 Testing PHPStan config generation...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create Laravel-like structure
        Path(tmpdir, "artisan").touch()
        Path(tmpdir, "app").mkdir()
        Path(tmpdir, "storage").mkdir()
        Path(tmpdir, "vendor").mkdir()
        Path(tmpdir, "composer.json").write_text('{"name": "test/laravel"}')
        
        # Create tools instance
        tools = ToolManager()
        
        # Test config creation
        result = await tools._create_phpstan_config(tmpdir)
        
        if result:
            config_file = Path(tmpdir, "phpstan.neon.dist")
            if config_file.exists():
                content = config_file.read_text()
                print("✅ Config created successfully!")
                print(f"📄 Config preview: {content[:500]}...")
                
                # Verify key elements
                checks = {
                    "level: 5": "level: 5" in content,
                    "paths: app": "- app" in content,
                    "excludes vendor": "vendor/*" in content,
                    "tmpDir storage": "tmpDir: storage/phpstan" in content,
                }
                
                print("🔍 Config validation:")
                for check_name, passed in checks.items():
                    status = "✅" if passed else "❌"
                    print(f"  {status} {check_name}")
                
                return all(checks.values())
        
        print("❌ Config creation failed")
        return False


async def test_stderr_cleaning():
    """Test stderr noise cleaning"""
    print("🧪 Testing stderr noise cleaning...")
    
    tools = ToolManager()
    
    # Test input with noise
    noisy_stderr = """huggingface/tokenizers: The current process just got forked, after parallelism has already been used. Disabling parallelism to avoid deadlocks...
To disable this warning, you can either:
        - Avoid using `tokenizers` before the fork if possible
        - Explicitly set the environment variable TOKENIZERS_PARALLELISM=(true | false)
 ------ --------------------------------------------------------------- 
  Line   app/Http/Controllers/Controller.php                           
 ------ --------------------------------------------------------------- 
  12     Undefined property: $user                                     
 ------ ---------------------------------------------------------------"""
    
    cleaned = tools._clean_stderr_noise(noisy_stderr)
    
    print(f"📊 Original stderr length: {len(noisy_stderr)} chars")
    print(f"📊 Cleaned stderr length: {len(cleaned)} chars")
    print(f"📊 Removed: {len(noisy_stderr) - len(cleaned)} chars")
    
    # Verify noise removed but real errors kept
    has_tokenizer_noise = "tokenizers" in cleaned.lower()
    has_real_error = "Undefined property" in cleaned
    
    print("🔍 Cleaning validation:")
    print(f"  {'✅' if not has_tokenizer_noise else '❌'} Tokenizer warnings removed")
    print(f"  {'✅' if has_real_error else '❌'} Real errors preserved")
    
    if not has_tokenizer_noise and has_real_error:
        print("✅ Cleaned stderr (real errors only):")
        print(cleaned.strip())
        return True
    
    return False


async def main():
    """Run all tests"""
    print("=" * 60)
    print("🚀 PHPStan Setup Test Suite")
    print("=" * 60)
    
    results = []
    
    # Test 1: Config generation
    results.append(await test_phpstan_config_generation())
    
    # Test 2: Stderr cleaning
    results.append(await test_stderr_cleaning())
    
    # Summary
    print("" + "=" * 60)
    print("📊 Test Results Summary")
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"✅ Passed: {passed}/{total}")
    print(f"{'🎉 ALL TESTS PASSED!' if all(results) else '❌ SOME TESTS FAILED'}")
    
    return all(results)


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)