#!/usr/bin/env python3
"""
Test du système d'orchestration d'agents complet - Parité Emergent.sh
Tests spécifiques pour valider le cycle complet d'orchestration
"""

import requests
import json
import time
import sys
from datetime import datetime

class OrchestrationSystemTester:
    def __init__(self):
        self.base_url = 'http://localhost:8001'
        self.api_url = f"{self.base_url}/api"
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []

    def log_test(self, name, success, details=""):
        """Log test result"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
        
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} - {name}")
        if details:
            print(f"    {details}")
        
        self.test_results.append({
            "name": name,
            "success": success,
            "details": details,
            "timestamp": datetime.now().isoformat()
        })

    def test_api_health(self):
        """Test 1: Vérifier que l'API est accessible"""
        try:
            response = requests.get(f"{self.api_url}/", timeout=10)
            success = response.status_code == 200
            details = f"Status: {response.status_code}, Response: {response.json()}"
            self.log_test("API Health Check", success, details)
            return success
        except Exception as e:
            self.log_test("API Health Check", False, f"Error: {e}")
            return False

    def test_create_python_run(self):
        """Test 2: Créer un run Python pour tester le cycle complet"""
        run_data = {
            "goal": "Create a simple Hello World Python file with a function that returns 'Hello, World!' and includes basic pytest tests",
            "stack": "python",
            "max_steps": 5,
            "max_retries_per_step": 2,
            "daily_budget_eur": 2.0
        }
        
        try:
            response = requests.post(f"{self.api_url}/runs", json=run_data, timeout=30)
            success = response.status_code in [200, 201]
            
            if success:
                run_info = response.json()
                run_id = run_info.get('id')
                details = f"Created Python run: {run_id}, Stack: {run_info.get('stack')}"
                self.log_test("Create Python Run", success, details)
                return run_id
            else:
                details = f"Status: {response.status_code}, Error: {response.text[:200]}"
                self.log_test("Create Python Run", success, details)
                return None
                
        except Exception as e:
            self.log_test("Create Python Run", False, f"Error: {e}")
            return None

    def test_create_laravel_run(self):
        """Test 3: Créer un run Laravel pour tester le cycle complet"""
        run_data = {
            "goal": "Create a simple Laravel API endpoint for user registration with validation and Pest tests",
            "stack": "laravel",
            "max_steps": 5,
            "max_retries_per_step": 2,
            "daily_budget_eur": 2.0
        }
        
        try:
            response = requests.post(f"{self.api_url}/runs", json=run_data, timeout=30)
            success = response.status_code in [200, 201]
            
            if success:
                run_info = response.json()
                run_id = run_info.get('id')
                details = f"Created Laravel run: {run_id}, Stack: {run_info.get('stack')}"
                self.log_test("Create Laravel Run", success, details)
                return run_id
            else:
                details = f"Status: {response.status_code}, Error: {response.text[:200]}"
                self.log_test("Create Laravel Run", success, details)
                return None
                
        except Exception as e:
            self.log_test("Create Laravel Run", False, f"Error: {e}")
            return None

    def monitor_run_progress(self, run_id, stack_name, max_wait_time=120):
        """Test 4: Surveiller le progrès d'un run et détecter les phases d'orchestration"""
        if not run_id:
            self.log_test(f"Monitor {stack_name} Run Progress", False, "No run ID provided")
            return False, {}

        print(f"\n🔍 Monitoring {stack_name} run {run_id} for {max_wait_time}s...")
        
        phases_detected = {
            "planning": False,
            "development": False,
            "testing": False,
            "review": False,
            "completion": False
        }
        
        agent_activity = {
            "planner_agent": False,
            "developer_agent": False,
            "reviewer_agent": False
        }
        
        start_time = time.time()
        last_step = 0
        
        while time.time() - start_time < max_wait_time:
            try:
                response = requests.get(f"{self.api_url}/runs/{run_id}", timeout=10)
                if response.status_code != 200:
                    continue
                
                run_data = response.json()
                status = run_data.get('status', 'unknown')
                current_step = run_data.get('current_step', 0)
                logs = run_data.get('logs', [])
                
                # Afficher le progrès si changement
                if current_step != last_step:
                    print(f"    Step {current_step}, Status: {status}, Logs: {len(logs)}")
                    last_step = current_step
                
                # Analyser les logs pour détecter les phases
                for log in logs[-5:]:  # Derniers 5 logs
                    content = log.get('content', '').lower()
                    
                    # Détecter les phases d'orchestration
                    if any(keyword in content for keyword in ['phase 1:', 'planning', 'generate plan']):
                        phases_detected["planning"] = True
                    elif any(keyword in content for keyword in ['phase 2:', 'execution', 'development']):
                        phases_detected["development"] = True
                    elif any(keyword in content for keyword in ['test', 'pytest', 'pest']):
                        phases_detected["testing"] = True
                    elif any(keyword in content for keyword in ['review', 'validation']):
                        phases_detected["review"] = True
                    elif any(keyword in content for keyword in ['completed', 'phase 3:', 'finalization']):
                        phases_detected["completion"] = True
                    
                    # Détecter l'activité des agents
                    if 'planneragent' in content or 'planner agent' in content:
                        agent_activity["planner_agent"] = True
                    elif 'developeragent' in content or 'developer agent' in content:
                        agent_activity["developer_agent"] = True
                    elif 'revieweragent' in content or 'reviewer agent' in content:
                        agent_activity["reviewer_agent"] = True
                
                # Vérifier si le run est terminé
                if status in ['completed', 'failed', 'cancelled']:
                    print(f"    🏁 Run finished with status: {status}")
                    break
                    
                time.sleep(5)  # Attendre 5 secondes avant la prochaine vérification
                
            except Exception as e:
                print(f"    Error monitoring run: {e}")
                time.sleep(5)
                continue
        
        # Analyser les résultats
        elapsed_time = time.time() - start_time
        
        # Obtenir l'état final
        try:
            response = requests.get(f"{self.api_url}/runs/{run_id}", timeout=10)
            final_data = response.json() if response.status_code == 200 else {}
        except:
            final_data = {}
        
        final_status = final_data.get('status', 'unknown')
        final_step = final_data.get('current_step', 0)
        final_logs = final_data.get('logs', [])
        
        # Évaluer le succès
        success_criteria = []
        
        # 1. Le run ne doit pas crasher
        if final_status != 'unknown':
            success_criteria.append("No system crash")
        
        # 2. Au moins la phase de planification doit être détectée
        if phases_detected["planning"]:
            success_criteria.append("Planning phase detected")
        
        # 3. Des étapes d'exécution doivent avoir lieu
        if final_step > 0:
            success_criteria.append("Execution steps performed")
        
        # 4. Des logs doivent être générés
        if len(final_logs) > 0:
            success_criteria.append("Logs generated")
        
        # 5. Au moins un agent doit être actif
        if any(agent_activity.values()):
            success_criteria.append("Agent activity detected")
        
        success = len(success_criteria) >= 3  # Au moins 3 critères sur 5
        
        details = f"Status: {final_status}, Steps: {final_step}, Phases: {sum(phases_detected.values())}/5, Agents: {sum(agent_activity.values())}/3, Time: {elapsed_time:.1f}s"
        self.log_test(f"Monitor {stack_name} Run Progress", success, details)
        
        return success, {
            "final_status": final_status,
            "final_step": final_step,
            "phases_detected": phases_detected,
            "agent_activity": agent_activity,
            "elapsed_time": elapsed_time,
            "logs_count": len(final_logs)
        }

    def test_agent_conversations(self, run_id, stack_name):
        """Test 5: Vérifier que les conversations d'agents sont sauvegardées"""
        if not run_id:
            self.log_test(f"Agent Conversations {stack_name}", False, "No run ID provided")
            return False
        
        try:
            response = requests.get(f"{self.api_url}/runs/{run_id}/agent-conversations", timeout=10)
            success = response.status_code == 200
            
            if success:
                conversations = response.json().get('conversations', [])
                details = f"Found {len(conversations)} agent conversations"
                self.log_test(f"Agent Conversations {stack_name}", success, details)
                return len(conversations) > 0
            else:
                details = f"Status: {response.status_code}"
                self.log_test(f"Agent Conversations {stack_name}", success, details)
                return False
                
        except Exception as e:
            self.log_test(f"Agent Conversations {stack_name}", False, f"Error: {e}")
            return False

    def test_project_isolation(self, run_id, stack_name):
        """Test 6: Vérifier l'isolation des projets"""
        if not run_id:
            self.log_test(f"Project Isolation {stack_name}", False, "No run ID provided")
            return False
        
        try:
            response = requests.get(f"{self.api_url}/projects/{run_id}", timeout=10)
            success = response.status_code == 200
            
            if success:
                project_info = response.json()
                details = f"Project isolated: {project_info.get('id', 'unknown')}, Stack: {project_info.get('stack', 'unknown')}"
                self.log_test(f"Project Isolation {stack_name}", success, details)
                return True
            else:
                details = f"Status: {response.status_code}"
                self.log_test(f"Project Isolation {stack_name}", success, details)
                return False
                
        except Exception as e:
            self.log_test(f"Project Isolation {stack_name}", False, f"Error: {e}")
            return False

    def test_export_functionality(self, run_id, stack_name):
        """Test 7: Tester la fonctionnalité d'export ZIP"""
        if not run_id:
            self.log_test(f"Export Functionality {stack_name}", False, "No run ID provided")
            return False
        
        try:
            # Test export ZIP
            response = requests.post(f"{self.api_url}/runs/{run_id}/export?export_format=zip", timeout=15)
            zip_success = response.status_code == 200
            
            # Test export GitHub preparation
            response = requests.post(f"{self.api_url}/runs/{run_id}/export?export_format=github", timeout=10)
            github_success = response.status_code == 200
            
            success = zip_success or github_success
            details = f"ZIP export: {'✅' if zip_success else '❌'}, GitHub prep: {'✅' if github_success else '❌'}"
            self.log_test(f"Export Functionality {stack_name}", success, details)
            return success
            
        except Exception as e:
            self.log_test(f"Export Functionality {stack_name}", False, f"Error: {e}")
            return False

    def test_validation_endpoints(self):
        """Test 8: Tester les endpoints de validation utilisateur"""
        # Créer un run de test pour la validation
        run_data = {
            "goal": "Test validation endpoints",
            "stack": "python",
            "max_steps": 1,
            "daily_budget_eur": 0.1
        }
        
        try:
            response = requests.post(f"{self.api_url}/runs", json=run_data, timeout=15)
            if response.status_code not in [200, 201]:
                self.log_test("Validation Endpoints", False, "Failed to create test run")
                return False
            
            run_id = response.json().get('id')
            if not run_id:
                self.log_test("Validation Endpoints", False, "No run ID returned")
                return False
            
            # Test validation du plan
            validation_data = {"approved": True, "feedback": "Test validation"}
            response = requests.post(f"{self.api_url}/runs/{run_id}/validate-plan", json=validation_data, timeout=10)
            plan_validation_success = response.status_code == 200
            
            # Test validation d'étape
            response = requests.post(f"{self.api_url}/runs/{run_id}/validate-step", json={"step_number": 1, **validation_data}, timeout=10)
            step_validation_success = response.status_code == 200
            
            # Test interruption
            response = requests.post(f"{self.api_url}/runs/{run_id}/interrupt", json={"reason": "Test interruption"}, timeout=10)
            interrupt_success = response.status_code == 200
            
            success = plan_validation_success and step_validation_success and interrupt_success
            details = f"Plan validation: {'✅' if plan_validation_success else '❌'}, Step validation: {'✅' if step_validation_success else '❌'}, Interrupt: {'✅' if interrupt_success else '❌'}"
            self.log_test("Validation Endpoints", success, details)
            return success
            
        except Exception as e:
            self.log_test("Validation Endpoints", False, f"Error: {e}")
            return False

    def test_dependency_installation_fallbacks(self):
        """Test 9: Tester l'installation des dépendances avec fallbacks"""
        try:
            # Vérifier les statistiques admin pour voir la configuration
            response = requests.get(f"{self.api_url}/admin/stats", timeout=10)
            success = response.status_code == 200
            
            if success:
                stats = response.json()
                settings = stats.get('settings', {})
                auto_create = settings.get('auto_create_structures', False)
                details = f"Auto-create structures: {auto_create}, Max retries: {settings.get('max_local_retries', 'unknown')}"
                self.log_test("Dependency Installation Config", success, details)
                return True
            else:
                details = f"Status: {response.status_code}"
                self.log_test("Dependency Installation Config", success, details)
                return False
                
        except Exception as e:
            self.log_test("Dependency Installation Config", False, f"Error: {e}")
            return False

    def test_github_integration(self):
        """Test 10: Tester l'intégration GitHub"""
        try:
            # Test OAuth URL generation
            response = requests.get(f"{self.api_url}/github/oauth-url", timeout=10)
            oauth_success = response.status_code == 200
            
            # Test auth endpoint avec code invalide (doit échouer gracieusement)
            auth_data = {"code": "invalid-test-code", "state": "test"}
            response = requests.post(f"{self.api_url}/github/auth", json=auth_data, timeout=10)
            auth_fail_success = response.status_code in [400, 500]  # Doit échouer
            
            success = oauth_success and auth_fail_success
            details = f"OAuth URL: {'✅' if oauth_success else '❌'}, Auth error handling: {'✅' if auth_fail_success else '❌'}"
            self.log_test("GitHub Integration", success, details)
            return success
            
        except Exception as e:
            self.log_test("GitHub Integration", False, f"Error: {e}")
            return False

    def run_comprehensive_tests(self):
        """Exécuter tous les tests du système d'orchestration"""
        print("🚀 TESTS DU SYSTÈME D'ORCHESTRATION D'AGENTS COMPLET")
        print("=" * 80)
        print("Validation du cycle complet de parité Emergent.sh")
        print("=" * 80)
        
        # Test 1: Santé de l'API
        if not self.test_api_health():
            print("❌ API non accessible - arrêt des tests")
            return False
        
        # Test 2-3: Créer les runs de test
        print(f"\n{'='*20} CRÉATION DES RUNS DE TEST {'='*20}")
        python_run_id = self.test_create_python_run()
        laravel_run_id = self.test_create_laravel_run()
        
        # Test 4: Surveiller le progrès des runs
        print(f"\n{'='*20} SURVEILLANCE DU CYCLE D'ORCHESTRATION {'='*20}")
        python_success, python_results = self.monitor_run_progress(python_run_id, "Python", 120)
        laravel_success, laravel_results = self.monitor_run_progress(laravel_run_id, "Laravel", 90)
        
        # Test 5: Conversations d'agents
        print(f"\n{'='*20} VALIDATION DES AGENTS {'='*20}")
        self.test_agent_conversations(python_run_id, "Python")
        self.test_agent_conversations(laravel_run_id, "Laravel")
        
        # Test 6: Isolation des projets
        print(f"\n{'='*20} ISOLATION DES PROJETS {'='*20}")
        self.test_project_isolation(python_run_id, "Python")
        self.test_project_isolation(laravel_run_id, "Laravel")
        
        # Test 7: Fonctionnalités d'export
        print(f"\n{'='*20} FONCTIONNALITÉS D'EXPORT {'='*20}")
        self.test_export_functionality(python_run_id, "Python")
        self.test_export_functionality(laravel_run_id, "Laravel")
        
        # Test 8-10: Autres fonctionnalités
        print(f"\n{'='*20} FONCTIONNALITÉS SYSTÈME {'='*20}")
        self.test_validation_endpoints()
        self.test_dependency_installation_fallbacks()
        self.test_github_integration()
        
        return True

    def print_final_results(self):
        """Afficher les résultats finaux"""
        print(f"\n{'='*80}")
        print("📊 RÉSULTATS FINAUX DES TESTS D'ORCHESTRATION")
        print(f"{'='*80}")
        print(f"Tests exécutés: {self.tests_run}")
        print(f"Tests réussis: {self.tests_passed}")
        print(f"Tests échoués: {self.tests_run - self.tests_passed}")
        
        if self.tests_run > 0:
            success_rate = (self.tests_passed / self.tests_run) * 100
            print(f"Taux de réussite: {success_rate:.1f}%")
            
            if success_rate >= 80:
                print("🎉 EXCELLENT - Système d'orchestration pleinement fonctionnel!")
            elif success_rate >= 60:
                print("✅ BON - Système d'orchestration largement fonctionnel")
            elif success_rate >= 40:
                print("⚠️  MOYEN - Système d'orchestration partiellement fonctionnel")
            else:
                print("❌ PROBLÉMATIQUE - Système d'orchestration nécessite des corrections")
        
        print(f"\n{'='*80}")
        
        # Résumé des tests critiques
        critical_tests = [
            "Create Python Run",
            "Create Laravel Run", 
            "Monitor Python Run Progress",
            "Monitor Laravel Run Progress"
        ]
        
        critical_passed = 0
        for result in self.test_results:
            if result["name"] in critical_tests and result["success"]:
                critical_passed += 1
        
        print(f"Tests critiques d'orchestration: {critical_passed}/{len(critical_tests)}")
        
        if critical_passed >= 3:
            print("✅ Le cycle d'orchestration d'agents fonctionne correctement")
        else:
            print("❌ Le cycle d'orchestration d'agents nécessite des corrections")

def main():
    tester = OrchestrationSystemTester()
    
    try:
        tester.run_comprehensive_tests()
    except KeyboardInterrupt:
        print("\n⚠️  Tests interrompus par l'utilisateur")
    except Exception as e:
        print(f"\n❌ Erreur lors des tests: {e}")
    finally:
        tester.print_final_results()
    
    return 0 if tester.tests_passed >= tester.tests_run * 0.6 else 1

if __name__ == "__main__":
    sys.exit(main())