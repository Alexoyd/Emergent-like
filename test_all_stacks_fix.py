#!/usr/bin/env python3
"""
Test script to verify all stack project creation works correctly
Tests Vue, React, Node, and Python project skeletons
"""
import asyncio
import sys
import tempfile
import shutil
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / 'backend'))

from orchestrator.project_manager import ProjectManager

async def test_stack_creation(stack: str, essential_files: list):
    """Test that a specific stack project is created with all essential files"""
    print(f"{'='*60}")
    print(f"🧪 Testing {stack.upper()} project creation...")
    print(f"{'='*60}")
    
    # Create a temporary project
    pm = ProjectManager()
    temp_base = Path(tempfile.mkdtemp())
    
    try:
        # Override projects_base_path for testing
        original_base = pm.projects_base_path
        pm.projects_base_path = temp_base
        
        test_project_id = f"test-{stack}-project"
        
        print(f"📁 Creating {stack} project in {temp_base / test_project_id}")
        
        # Create project workspace
        result = await pm.create_project_workspace(
            project_id=test_project_id,
            stack=stack,
            project_name=f"Test {stack.capitalize()} App"
        )
        
        code_path = Path(result["code_path"])
        
        # Check essential files
        print("🔍 Checking for essential files:")
        all_good = True
        for file in essential_files:
            file_path = code_path / file
            exists = file_path.exists()
            status = "✅" if exists else "❌"
            print(f"  {status} {file}")
            if not exists:
                all_good = False
                print(f"      Missing: {file_path}")
        
        # Restore original path
        pm.projects_base_path = original_base
        
        if all_good:
            print(f"✅ SUCCESS! All {stack} files created correctly")
            return True
        else:
            print(f"❌ FAILURE! Some {stack} files are missing")
            return False
            
    except Exception as e:
        print(f"❌ ERROR during {stack} test: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Cleanup
        if temp_base.exists():
            shutil.rmtree(temp_base)

async def test_all_stacks():
    """Test all supported stacks"""
    print("🚀 Testing project creation fix for ALL stacks")
    print("="*60)
    
    stacks_to_test = {
        "vue": [
            "package.json",
            "vite.config.js",
            "index.html",
            "src/App.vue",
            "src/main.js",
            "src/components/Counter.vue",
        ],
        "react": [
            "package.json",
            "src/App.js",
            "src/index.js",
            "public/index.html",
        ],
        "node": [
            "package.json",
            "src/index.js",
            "src/server.js",
        ],
        "python": [
            "requirements.txt",
            "src/__init__.py",
            "tests/__init__.py",
        ],
    }
    
    results = {}
    for stack, files in stacks_to_test.items():
        results[stack] = await test_stack_creation(stack, files)
    
    # Summary
    print("" + "="*60)
    print("📊 SUMMARY")
    print("="*60)
    
    all_passed = True
    for stack, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {stack.upper()}")
        if not passed:
            all_passed = False
    
    if all_passed:
        print("🎉 ALL STACKS FIXED! Project creation works correctly for all stacks.")
    else:
        print("⚠️  Some stacks still have issues. Check the logs above.")
    
    return all_passed

if __name__ == "__main__":
    result = asyncio.run(test_all_stacks())
    sys.exit(0 if result else 1)