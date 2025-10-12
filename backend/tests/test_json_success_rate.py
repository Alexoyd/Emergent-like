"""
Script pour mesurer le taux de succès JSON de developer_direct.py
Mesure combien de fois le LLM génère du JSON valide au premier essai
"""

import asyncio
import sys
import os
from pathlib import Path
import logging

sys.path.insert(0, str(Path(__file__).parent.parent))

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Mock environment
os.environ["MONGO_URL"] = "mongodb://localhost:27017/test_db"
os.environ["FILE_WRITE_MODE"] = "direct"
os.environ["DEVELOPMENT_MODE"] = "false"  # Use real LLM
os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY", "test_key")

from orchestrator.agents.developer_direct import DeveloperAgentDirect
from orchestrator.schemas import DeveloperOutput


async def test_json_generation(scenario: str, goal: str, plan_summary: str, context: dict) -> dict:
    """
    Test une génération JSON et retourne le résultat
    """
    agent = DeveloperAgentDirect()
    
    try:
        result = await agent.generate_operations(
            goal=goal,
            plan_summary=plan_summary,
            context=context
        )
        
        return {
            "scenario": scenario,
            "success": result.validated,
            "attempts": result.attempts,
            "operations_count": len(result.operations) if result.validated else 0,
            "error": None
        }
    except Exception as e:
        return {
            "scenario": scenario,
            "success": False,
            "attempts": 3,
            "operations_count": 0,
            "error": str(e)
        }


async def main():
    """
    Execute plusieurs scénarios de test pour mesurer le taux de succès
    """
    
    scenarios = [
        {
            "name": "Simple file creation",
            "goal": "Create a simple README.md file",
            "plan": "Step 1: Create README.md with basic project description",
            "context": {
                "step_number": 1,
                "step_title": "Create README",
                "stack": "node",
                "project_structure": {"files": [], "dirs": []},
                "existing_files": []
            }
        },
        {
            "name": "Laravel route creation",
            "goal": "Add a new API route for users",
            "plan": "Step 1: Create routes/api.php with user endpoint",
            "context": {
                "step_number": 1,
                "step_title": "Add user route",
                "stack": "php",
                "project_structure": {
                    "files": ["routes/web.php", "app/Http/Controllers/Controller.php"],
                    "dirs": ["routes", "app/Http/Controllers"]
                },
                "existing_files": ["routes/web.php"]
            }
        },
        {
            "name": "React component creation",
            "goal": "Create a Header component",
            "plan": "Step 1: Create src/components/Header.jsx",
            "context": {
                "step_number": 1,
                "step_title": "Create Header component",
                "stack": "react",
                "project_structure": {
                    "files": ["src/App.jsx", "src/index.js"],
                    "dirs": ["src", "src/components"]
                },
                "existing_files": ["src/App.jsx"]
            }
        },
        {
            "name": "Python API endpoint",
            "goal": "Add a FastAPI endpoint for health check",
            "plan": "Step 1: Update main.py with /health endpoint",
            "context": {
                "step_number": 1,
                "step_title": "Add health endpoint",
                "stack": "python",
                "project_structure": {
                    "files": ["main.py", "requirements.txt"],
                    "dirs": []
                },
                "existing_files": ["main.py"]
            }
        },
        {
            "name": "Multi-file creation",
            "goal": "Create a complete user module with model, controller, and route",
            "plan": "Step 1: Create user module files\nStep 2: Add user routes\nStep 3: Connect to database",
            "context": {
                "step_number": 1,
                "step_title": "Create user module",
                "stack": "php",
                "project_structure": {
                    "files": ["app/Http/Controllers/Controller.php"],
                    "dirs": ["app/Models", "app/Http/Controllers", "routes"]
                },
                "existing_files": ["app/Http/Controllers/Controller.php"]
            }
        }
    ]
    
    results = []
    
    logger.info("=" * 80)
    logger.info("🧪 MEASURING JSON SUCCESS RATE FOR DEVELOPER_DIRECT")
    logger.info("=" * 80)
    
    for i, scenario in enumerate(scenarios, 1):
        logger.info(f"\n📋 Scenario {i}/{len(scenarios)}: {scenario['name']}")
        
        result = await test_json_generation(
            scenario=scenario['name'],
            goal=scenario['goal'],
            plan_summary=scenario['plan'],
            context=scenario['context']
        )
        
        results.append(result)
        
        if result['success']:
            logger.info(f"✅ SUCCESS in {result['attempts']} attempt(s) - {result['operations_count']} operations")
        else:
            logger.info(f"❌ FAILED after {result['attempts']} attempts - Error: {result['error']}")
    
    # Calculate statistics
    total = len(results)
    successes = sum(1 for r in results if r['success'])
    first_try_successes = sum(1 for r in results if r['success'] and r['attempts'] == 1)
    
    success_rate = (successes / total * 100) if total > 0 else 0
    first_try_rate = (first_try_successes / total * 100) if total > 0 else 0
    
    avg_attempts = sum(r['attempts'] for r in results) / total if total > 0 else 0
    
    # Generate report
    logger.info("\n" + "=" * 80)
    logger.info("📊 JSON GENERATION SUCCESS RATE REPORT")
    logger.info("=" * 80)
    logger.info(f"Total scenarios tested: {total}")
    logger.info(f"Successful generations: {successes}/{total} ({success_rate:.1f}%)")
    logger.info(f"First-try successes: {first_try_successes}/{total} ({first_try_rate:.1f}%)")
    logger.info(f"Average attempts per scenario: {avg_attempts:.2f}")
    logger.info("=" * 80)
    
    # Detailed results
    logger.info("\n📋 DETAILED RESULTS:")
    for r in results:
        status = "✅" if r['success'] else "❌"
        logger.info(f"{status} {r['scenario']}: {r['attempts']} attempts, {r['operations_count']} operations")
        if r['error']:
            logger.info(f"   Error: {r['error']}")
    
    # Save report
    report_path = Path(__file__).parent / "json_success_rate_report.txt"
    with open(report_path, "w") as f:
        f.write("JSON GENERATION SUCCESS RATE REPORT\n")
        f.write("=" * 80 + "\n\n")
        f.write(f"Total scenarios tested: {total}\n")
        f.write(f"Successful generations: {successes}/{total} ({success_rate:.1f}%)\n")
        f.write(f"First-try successes: {first_try_successes}/{total} ({first_try_rate:.1f}%)\n")
        f.write(f"Average attempts per scenario: {avg_attempts:.2f}\n\n")
        f.write("DETAILED RESULTS:\n")
        f.write("-" * 80 + "\n")
        for r in results:
            status = "SUCCESS" if r['success'] else "FAILED"
            f.write(f"{status}: {r['scenario']}\n")
            f.write(f"  Attempts: {r['attempts']}\n")
            f.write(f"  Operations: {r['operations_count']}\n")
            if r['error']:
                f.write(f"  Error: {r['error']}\n")
            f.write("\n")
    
    logger.info(f"\n📄 Report saved to: {report_path}")
    
    return {
        "total": total,
        "successes": successes,
        "first_try_successes": first_try_successes,
        "success_rate": success_rate,
        "first_try_rate": first_try_rate,
        "avg_attempts": avg_attempts
    }


if __name__ == "__main__":
    # Check if OpenAI API key is set
    if os.getenv("OPENAI_API_KEY", "test_key") == "test_key":
        logger.warning("⚠️ OPENAI_API_KEY not set - using test mode")
        logger.warning("⚠️ For real testing, set OPENAI_API_KEY environment variable")
        logger.warning("⚠️ Results may not be accurate in test mode")
    
    stats = asyncio.run(main())
    
    # Exit with appropriate code
    sys.exit(0 if stats['success_rate'] >= 80 else 1)
