#!/usr/bin/env python3
"""
Test script to verify Vue.js project creation fix
This tests that src/App.vue is properly created when a Vue project is initialized
"""
import asyncio
import sys
import tempfile
import shutil
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / 'backend'))

from orchestrator.project_manager import ProjectManager

async def test_vue_project_creation():
    """Test that Vue.js projects are created with all essential files"""
    print("🧪 Testing Vue.js project creation fix...")
    
    # Create a temporary project
    pm = ProjectManager()
    temp_base = Path(tempfile.mkdtemp())
    
    try:
        # Override projects_base_path for testing
        original_base = pm.projects_base_path
        pm.projects_base_path = temp_base
        
        test_project_id = "test-vue-project-fix"
        
        print(f"📁 Creating Vue.js project in {temp_base / test_project_id}")
        
        # Create project workspace (this should now use VueHandler.create_project_skeleton)
        result = await pm.create_project_workspace(
            project_id=test_project_id,
            stack="vue",
            project_name="Test Vue App"
        )
        
        code_path = Path(result["code_path"])
        
        # Check essential files
        essential_files = [
            "package.json",
            "vite.config.js",
            "index.html",
            "src/App.vue",
            "src/main.js",
            "src/components/Counter.vue",
        ]
        
        print("🔍 Checking for essential files:")
        all_good = True
        for file in essential_files:
            file_path = code_path / file
            exists = file_path.exists()
            status = "✅" if exists else "❌"
            print(f"  {status} {file}")
            if not exists:
                all_good = False
        
        # Check src/App.vue content
        app_vue_path = code_path / "src/App.vue"
        if app_vue_path.exists():
            content = app_vue_path.read_text()
            has_template = "<template>" in content
            has_script = "<script>" in content
            has_style = "<style>" in content
            
            print("📄 src/App.vue content analysis:")
            print(f"  {'✅' if has_template else '❌'} Has <template> section")
            print(f"  {'✅' if has_script else '❌'} Has <script> section")
            print(f"  {'✅' if has_style else '❌'} Has <style> section")
            
            if not (has_template and has_script and has_style):
                all_good = False
        
        # Restore original path
        pm.projects_base_path = original_base
        
        if all_good:
            print("✅ SUCCESS! All Vue.js files created correctly")
            print("The bug is FIXED - src/App.vue now exists from the start!")
            return True
        else:
            print("❌ FAILURE! Some files are missing")
            print("The bug still exists - check project_manager.py")
            return False
            
    except Exception as e:
        print(f"❌ ERROR during test: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Cleanup
        if temp_base.exists():
            shutil.rmtree(temp_base)
            print(f"🧹 Cleaned up test directory: {temp_base}")

if __name__ == "__main__":
    result = asyncio.run(test_vue_project_creation())
    sys.exit(0 if result else 1)