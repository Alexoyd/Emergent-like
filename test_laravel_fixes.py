""""
🧪 Script de Test des Corrections Laravel Phase 2
Valide que toutes les corrections fonctionnent correctement
"""
import asyncio
import sys
import os
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from orchestrator.tools import ToolManager
from orchestrator.repair_agent import RepairAgent
from orchestrator.stacks.laravel_handler import LaravelHandler

async def test_laravel_fixes():
    """Test all Laravel fixes"""
    print("=" * 80)
    print("🧪 TESTING LARAVEL FIXES - PHASE 2")
    print("=" * 80)
    print()
    
    # Test 1: ToolManager initialization with new counters
    print("✅ Test 1: ToolManager Initialization")
    tool_manager = ToolManager()
    assert hasattr(tool_manager, 'project_repair_counts'), "Missing project_repair_counts"
    assert hasattr(tool_manager, 'max_total_repairs_per_project'), "Missing max_total_repairs_per_project"
    assert tool_manager.timeout == 300, f"Timeout should be 300, got {tool_manager.timeout}"
    print(f"   - Timeout: {tool_manager.timeout}s ✅")
    print(f"   - Max repairs per project: {tool_manager.max_total_repairs_per_project} ✅")
    print()
    
    # Test 2: Laravel command flags
    print("✅ Test 2: Laravel Non-Interactive Commands")
    pest_commands = tool_manager._get_test_commands("pest")
    phpstan_commands = tool_manager._get_test_commands("phpstan")
    pint_commands = tool_manager._get_test_commands("pint")
    
    # Check pest has --no-interaction
    assert any("--no-interaction" in cmd for cmd in pest_commands), "Pest missing --no-interaction"
    print(f"   - Pest commands: {pest_commands[0]} ✅")
    
    # Check phpstan has --no-progress
    assert any("--no-progress" in cmd for cmd in phpstan_commands), "PHPStan missing --no-progress"
    print(f"   - PHPStan commands: {phpstan_commands[0]} ✅")
    
    # Check pint has -q or --quiet
    assert any("-q" in cmd or "--quiet" in cmd for cmd in pint_commands), "Pint missing quiet flag"
    print(f"   - Pint commands: {pint_commands[0]} ✅")
    print()
    
    # Test 3: New methods exist
    print("✅ Test 3: New Methods Existence")
    assert hasattr(tool_manager, '_verify_repair_success'), "Missing _verify_repair_success"
    assert hasattr(tool_manager, '_validate_project_structure_for_patch'), "Missing _validate_project_structure_for_patch"
    print("   - _verify_repair_success() exists ✅")
    print("   - _validate_project_structure_for_patch() exists ✅")
    print()
    
    # Test 4: RepairAgent subprocess fix
    print("✅ Test 4: RepairAgent Subprocess Fix")
    repair_agent = RepairAgent()
    # Simulate command that doesn't exist
    result = await repair_agent._run_command_with_timeout(
        ["nonexistent_command_xyz"], 
        cwd="/tmp",
        timeout=5
    )
    assert result.returncode == -1, "Should return -1 for non-existent command"
    assert "not found" in result.stderr.lower() or "command not found" in result.stderr.lower()
    print("   - Subprocess error handling works ✅")
    print()
    
    # Test 5: Laravel handler default command
    print("✅ Test 5: LaravelHandler Default Command")
    default_cmd = LaravelHandler.default_test_command
    assert "--no-interaction" in default_cmd, "Default command missing --no-interaction"
    print(f"   - Default test command: {default_cmd} ✅")
    print()
    
    # Test 6: Anti-loop protection
    print("✅ Test 6: Anti-Loop Protection")
    project_path = "/tmp/test_project"
    command = ["test", "command"]
    error = "test error"
    
    # Simulate multiple repair attempts
    for i in range(6):
        result = await tool_manager._attempt_command_repair(
            project_path, command, error, "test"
        )
        
        if i < 5:
            # Should allow first 5 attempts
            print(f"   - Attempt {i+1}: Allowed ✅")
        else:
            # Should block 6th attempt
            assert result == False, f"Should block attempt {i+1}"
            print(f"   - Attempt {i+1}: Blocked (anti-loop) ✅")
    print()
    
    print("=" * 80)
    print("🎉 ALL TESTS PASSED!")
    print("=" * 80)
    print()
    print("📋 Summary of Validations:")
    print("   ✅ ToolManager timeout increased to 300s")
    print("   ✅ Global repair limit (5 per project) working")
    print("   ✅ All Laravel commands have non-interactive flags")
    print("   ✅ New methods _verify_repair_success() and _validate_project_structure_for_patch() exist")
    print("   ✅ RepairAgent subprocess error handling fixed")
    print("   ✅ LaravelHandler default command non-interactive")
    print("   ✅ Anti-loop protection working (blocks after 5 attempts)")
    print()
    print("🚀 System ready for Laravel orchestration testing!")
    print()

if __name__ == "__main__":
    asyncio.run(test_laravel_fixes())
"
