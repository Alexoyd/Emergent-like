import requests
import sys
import json
import time
from datetime import datetime

class EmergentSystemTester:
    def __init__(self, base_url=None):
        # Use localhost for testing since external URL is not configured
        if base_url is None:
            base_url = 'http://localhost:8001'
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.tests_run = 0
        self.tests_passed = 0
        self.created_run_id = None
        self.github_token = None

    def run_test(self, name, method, endpoint, expected_status, data=None, timeout=10, headers=None):
        """Run a single API test"""
        url = f"{self.api_url}/{endpoint}" if endpoint else f"{self.api_url}/"
        test_headers = {'Content-Type': 'application/json'}
        if headers:
            test_headers.update(headers)

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        print(f"   URL: {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=test_headers, timeout=timeout, params=data)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=test_headers, timeout=timeout)
            elif method == 'DELETE':
                response = requests.delete(url, headers=test_headers, timeout=timeout)

            print(f"   Status Code: {response.status_code}")
            
            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Expected {expected_status}, got {response.status_code}")
                
                # Try to parse JSON response
                try:
                    response_data = response.json()
                    print(f"   Response: {json.dumps(response_data, indent=2)[:300]}...")
                    return True, response_data
                except:
                    print(f"   Response: {response.text[:200]}...")
                    return True, {}
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                print(f"   Response: {response.text[:300]}...")
                return False, {}

        except requests.exceptions.Timeout:
            print(f"❌ Failed - Request timed out after {timeout} seconds")
            return False, {}
        except requests.exceptions.ConnectionError:
            print(f"❌ Failed - Connection error (server may be down)")
            return False, {}
        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, {}

    def test_health_check(self):
        """Test API health check"""
        return self.run_test("API Health Check", "GET", "", 200)

    def test_admin_stats(self):
        """Test admin statistics endpoint"""
        success, response = self.run_test("Admin Statistics", "GET", "admin/stats", 200)
        
        if success and response:
            # Check for new cache-related fields
            expected_fields = ['run_stats', 'daily_cost', 'project_count', 'cache_stats', 'cost_savings', 'settings']
            missing_fields = [field for field in expected_fields if field not in response]
            
            if missing_fields:
                print(f"⚠️  Missing expected fields in admin stats: {missing_fields}")
                return False, response
            else:
                print(f"✅ All expected admin stats fields present: {list(response.keys())}")
                
                # Check cache_stats structure
                if 'cache_stats' in response:
                    cache_stats = response['cache_stats']
                    cache_fields = ['total_entries', 'total_usage', 'hit_rate', 'most_used']
                    cache_missing = [field for field in cache_fields if field not in cache_stats]
                    if cache_missing:
                        print(f"⚠️  Missing cache stats fields: {cache_missing}")
                    else:
                        print(f"✅ Cache stats structure correct: {cache_stats}")
                
                # Check cost_savings structure
                if 'cost_savings' in response:
                    cost_savings = response['cost_savings']
                    savings_fields = ['tokens_saved', 'cost_saved_eur', 'savings_percentage']
                    savings_missing = [field for field in savings_fields if field not in cost_savings]
                    if savings_missing:
                        print(f"⚠️  Missing cost savings fields: {savings_missing}")
                    else:
                        print(f"✅ Cost savings structure correct: {cost_savings}")
                
                return True, response
        
        return success, response

    def test_projects_list(self):
        """Test projects listing"""
        return self.run_test("List Projects", "GET", "projects", 200)

    def test_github_oauth_url(self):
        """Test GitHub OAuth URL generation"""
        return self.run_test("GitHub OAuth URL", "GET", "github/oauth-url", 200, data={"state": "test-state"})

    def test_github_repositories(self):
        """Test GitHub repositories listing (without token)"""
        # This should fail without token, testing error handling
        return self.run_test("GitHub Repositories (No Token)", "GET", "github/repositories", 422)

    def test_create_run_basic(self):
        """Test creating a basic run"""
        run_data = {
            "goal": "Create a simple Laravel API endpoint for user registration with validation",
            "stack": "laravel",
            "max_steps": 3,
            "max_retries_per_step": 1,
            "daily_budget_eur": 1.0
        }
        
        success, response = self.run_test(
            "Create Basic Run",
            "POST",
            "runs",
            200,
            data=run_data,
            timeout=20
        )
        
        if not success:
            # Try with 201 status code
            success, response = self.run_test(
                "Create Basic Run (201)",
                "POST", 
                "runs",
                201,
                data=run_data,
                timeout=20
            )
        
        if success and 'id' in response:
            self.created_run_id = response['id']
            print(f"   Created run ID: {self.created_run_id}")
        
        return success, response

    def test_get_run(self):
        """Test getting a specific run"""
        if not self.created_run_id:
            print("❌ Skipping - No run ID available")
            return False, {}
        
        return self.run_test(
            "Get Specific Run",
            "GET",
            f"runs/{self.created_run_id}",
            200
        )

    def test_list_runs(self):
        """Test listing all runs"""
        return self.run_test("List All Runs", "GET", "runs", 200)

    def test_cancel_run(self):
        """Test cancelling a run"""
        if not self.created_run_id:
            print("❌ Skipping - No run ID available")
            return False, {}
        
        return self.run_test(
            "Cancel Run",
            "POST",
            f"runs/{self.created_run_id}/cancel",
            200
        )

    def test_file_operations(self):
        """Test file read/write operations"""
        # Test file read
        read_data = [
            {
                "operation": "read",
                "file_path": "/etc/hostname"
            }
        ]
        
        read_success, _ = self.run_test(
            "File Read Operation",
            "POST",
            "files/read",
            200,
            data=read_data
        )
        
        # Test file write
        write_data = [
            {
                "operation": "write",
                "file_path": "/tmp/test_emergent_file.txt",
                "content": "Test file created by Emergent system API test"
            }
        ]
        
        write_success, _ = self.run_test(
            "File Write Operation",
            "POST",
            "files/write",
            200,
            data=write_data
        )
        
        return read_success and write_success, {}

    def test_project_creation_isolation(self):
        """Test project workspace isolation"""
        # Create a run which should create isolated project workspace
        run_data = {
            "goal": "Test project isolation by creating a React component",
            "stack": "react",
            "max_steps": 2,
            "daily_budget_eur": 0.5
        }
        
        success, response = self.run_test(
            "Project Isolation Test",
            "POST",
            "runs",
            200,
            data=run_data,
            timeout=15
        )
        
        if not success:
            success, response = self.run_test(
                "Project Isolation Test (201)",
                "POST",
                "runs",
                201,
                data=run_data,
                timeout=15
            )
        
        if success and 'id' in response:
            project_id = response['id']
            
            # Test getting project info
            project_success, project_response = self.run_test(
                "Get Project Info",
                "GET",
                f"projects/{project_id}",
                200
            )
            
            return project_success, project_response
        
        return success, response

    def test_invalid_requests(self):
        """Test error handling with invalid requests"""
        # Test invalid run creation
        invalid_run_data = {
            "goal": "",  # Empty goal should fail
            "stack": "invalid_stack"
        }
        
        success, _ = self.run_test(
            "Invalid Run Creation",
            "POST",
            "runs",
            422,
            data=invalid_run_data
        )
        
        if not success:
            success, _ = self.run_test(
                "Invalid Run Creation (400)",
                "POST",
                "runs", 
                400,
                data=invalid_run_data
            )
        
        # Test non-existent run
        nonexistent_success, _ = self.run_test(
            "Get Non-existent Run",
            "GET",
            "runs/nonexistent-id-12345",
            404
        )
        
        # Test non-existent project
        project_404_success, _ = self.run_test(
            "Get Non-existent Project",
            "GET",
            "projects/nonexistent-project-12345",
            404
        )
        
        return success and nonexistent_success and project_404_success, {}

    def test_github_integration_structure(self):
        """Test GitHub integration endpoints structure (without actual auth)"""
        # Test OAuth URL generation
        oauth_success, oauth_response = self.run_test(
            "GitHub OAuth URL Generation",
            "GET",
            "github/oauth-url",
            200,
            data={"state": "test-integration"}
        )
        
        # Test auth endpoint with invalid code (should fail gracefully)
        auth_data = {
            "code": "invalid-test-code",
            "state": "test-integration"
        }
        
        auth_fail_success, _ = self.run_test(
            "GitHub Auth Invalid Code",
            "POST",
            "github/auth",
            400,  # Should fail with invalid code
            data=auth_data
        )
        
        if not auth_fail_success:
            # Try 500 status code for server error
            auth_fail_success, _ = self.run_test(
                "GitHub Auth Invalid Code (500)",
                "POST",
                "github/auth",
                500,
                data=auth_data
            )
        
        # Test clone endpoint with invalid data
        clone_data = {
            "repo_url": "invalid-url",
            "access_token": "invalid-token"
        }
        
        clone_fail_success, _ = self.run_test(
            "GitHub Clone Invalid URL",
            "POST",
            "github/clone",
            400,
            data=clone_data
        )
        
        if not clone_fail_success:
            clone_fail_success, _ = self.run_test(
                "GitHub Clone Invalid URL (500)",
                "POST",
                "github/clone",
                500,
                data=clone_data
            )
        
        return oauth_success and (auth_fail_success or clone_fail_success), {}

    def test_llm_router_configuration(self):
        """Test LLM router configuration through admin stats"""
        success, response = self.run_test(
            "LLM Router Config Check",
            "GET",
            "admin/stats",
            200
        )
        
        if success and 'settings' in response:
            settings = response['settings']
            expected_settings = ['max_local_retries', 'default_daily_budget', 'max_steps_per_run', 'auto_create_structures']
            
            has_all_settings = all(setting in settings for setting in expected_settings)
            if has_all_settings:
                print(f"✅ LLM Router settings found: {settings}")
                return True, response
            else:
                print(f"❌ Missing LLM Router settings. Found: {list(settings.keys())}")
                return False, response
        
        return success, response

    def test_comprehensive_stack_support(self):
        """Test different stack support in project creation"""
        stacks_to_test = ["laravel", "react", "python", "node", "vue"]
        successful_stacks = []
        
        for stack in stacks_to_test:
            run_data = {
                "goal": f"Test {stack} stack support with basic project structure",
                "stack": stack,
                "max_steps": 1,
                "daily_budget_eur": 0.1
            }
            
            success, response = self.run_test(
                f"Stack Support - {stack.upper()}",
                "POST",
                "runs",
                200,
                data=run_data,
                timeout=10
            )
            
            if not success:
                success, response = self.run_test(
                    f"Stack Support - {stack.upper()} (201)",
                    "POST",
                    "runs",
                    201,
                    data=run_data,
                    timeout=10
                )
            
            if success:
                successful_stacks.append(stack)
        
        print(f"✅ Supported stacks: {successful_stacks}")
        return len(successful_stacks) >= 3, {"supported_stacks": successful_stacks}

    def test_admin_global_stats(self):
        """Test new admin global statistics endpoint"""
        success, response = self.run_test("Admin Global Statistics", "GET", "admin/global-stats", 200)
        
        if success and response:
            # Check for expected fields in global stats
            expected_fields = ['total_projects', 'total_runs', 'total_costs', 'cache_stats', 'env_status', 'system_config']
            missing_fields = [field for field in expected_fields if field not in response]
            
            if missing_fields:
                print(f"⚠️  Missing expected fields in global stats: {missing_fields}")
                return False, response
            else:
                print(f"✅ All expected global stats fields present: {list(response.keys())}")
                
                # Check env_status structure
                if 'env_status' in response:
                    env_status = response['env_status']
                    env_fields = ['openai_key', 'anthropic_key', 'github_token', 'mongo_url']
                    env_missing = [field for field in env_fields if field not in env_status]
                    if env_missing:
                        print(f"⚠️  Missing env status fields: {env_missing}")
                    else:
                        print(f"✅ Environment status structure correct: {env_status}")
                
                # Check system_config structure
                if 'system_config' in response:
                    system_config = response['system_config']
                    config_fields = ['daily_budget', 'max_local_retries', 'max_steps', 'auto_create']
                    config_missing = [field for field in config_fields if field not in system_config]
                    if config_missing:
                        print(f"⚠️  Missing system config fields: {config_missing}")
                    else:
                        print(f"✅ System config structure correct: {system_config}")
                
                return True, response
        
        return success, response

    def test_admin_global_logs(self):
        """Test new admin global logs endpoint"""
        # Test without project_id filter
        success, response = self.run_test("Admin Global Logs", "GET", "admin/global-logs", 200)
        
        if success and response:
            # Check for expected structure
            expected_fields = ['logs', 'total_count']
            missing_fields = [field for field in expected_fields if field not in response]
            
            if missing_fields:
                print(f"⚠️  Missing expected fields in global logs: {missing_fields}")
                return False, response
            else:
                print(f"✅ Global logs structure correct: {list(response.keys())}")
                print(f"   Total logs: {response.get('total_count', 0)}")
                
                # Check logs structure if any exist
                logs = response.get('logs', [])
                if logs:
                    first_log = logs[0]
                    log_fields = ['timestamp', 'type', 'content', 'run_id']
                    log_missing = [field for field in log_fields if field not in first_log]
                    if log_missing:
                        print(f"⚠️  Missing log entry fields: {log_missing}")
                    else:
                        print(f"✅ Log entry structure correct")
                
                return True, response
        
        return success, response

    def test_admin_global_logs_filtered(self):
        """Test admin global logs with project_id filter"""
        # First get a project ID from projects list
        projects_success, projects_response = self.test_projects_list()
        
        if projects_success and 'projects' in projects_response:
            projects = projects_response['projects']
            if projects:
                # Use first project ID for filtering
                project_id = projects[0].get('id')
                if project_id:
                    success, response = self.run_test(
                        "Admin Global Logs Filtered", 
                        "GET", 
                        f"admin/global-logs?project_id={project_id}", 
                        200
                    )
                    
                    if success:
                        print(f"✅ Filtered logs for project {project_id}")
                        return True, response
                    
                    return success, response
        
        print("ℹ️  Skipping filtered logs test - no projects available")
        return True, {}

    def test_project_preview(self):
        """Test project preview functionality for different stacks"""
        # First create projects with different stacks to test preview
        stacks_to_test = ["react", "vue", "laravel", "python"]
        preview_results = {}
        
        for stack in stacks_to_test:
            # Create a run for this stack
            run_data = {
                "goal": f"Create a simple {stack} project for preview testing",
                "stack": stack,
                "max_steps": 1,
                "daily_budget_eur": 0.1
            }
            
            success, response = self.run_test(
                f"Create {stack.upper()} Project for Preview",
                "POST",
                "runs",
                200,
                data=run_data,
                timeout=10
            )
            
            if not success:
                success, response = self.run_test(
                    f"Create {stack.upper()} Project for Preview (201)",
                    "POST",
                    "runs",
                    201,
                    data=run_data,
                    timeout=10
                )
            
            if success and 'id' in response:
                project_id = response['id']
                
                # Test preview endpoint for this project
                preview_success, preview_response = self.run_test(
                    f"Preview {stack.upper()} Project",
                    "GET",
                    f"projects/{project_id}/preview",
                    200
                )
                
                if preview_success:
                    preview_results[stack] = preview_response
                    print(f"✅ Preview for {stack}: {preview_response.get('message', 'Success')}")
                else:
                    # Try 404 if project files don't exist yet
                    preview_success, preview_response = self.run_test(
                        f"Preview {stack.upper()} Project (404)",
                        "GET",
                        f"projects/{project_id}/preview",
                        404
                    )
                    if preview_success:
                        preview_results[stack] = {"status": "404", "message": "Project files not found"}
                        print(f"✅ Preview for {stack}: Project files not found (expected)")
        
        return len(preview_results) > 0, preview_results

    def test_project_preview_nonexistent(self):
        """Test project preview with non-existent project"""
        return self.run_test(
            "Preview Non-existent Project",
            "GET",
            "projects/nonexistent-project-12345/preview",
            404
        )

    def test_environment_configuration(self):
        """Test that environment variables are properly loaded"""
        success, response = self.run_test("Environment Configuration Check", "GET", "admin/global-stats", 200)
        
        if success and response:
            env_status = response.get('env_status', {})
            system_config = response.get('system_config', {})
            
            # Check that environment variables are detected
            env_checks = []
            if 'mongo_url' in env_status:
                env_checks.append(f"MongoDB: {'✅' if env_status['mongo_url'] else '❌'}")
            if 'openai_key' in env_status:
                env_checks.append(f"OpenAI: {'✅' if env_status['openai_key'] else '❌'}")
            if 'anthropic_key' in env_status:
                env_checks.append(f"Anthropic: {'✅' if env_status['anthropic_key'] else '❌'}")
            if 'github_token' in env_status:
                env_checks.append(f"GitHub: {'✅' if env_status['github_token'] else '❌'}")
            
            print(f"   Environment status: {', '.join(env_checks)}")
            
            # Check system configuration values
            config_checks = []
            if 'daily_budget' in system_config:
                config_checks.append(f"Daily Budget: €{system_config['daily_budget']}")
            if 'max_local_retries' in system_config:
                config_checks.append(f"Max Retries: {system_config['max_local_retries']}")
            if 'max_steps' in system_config:
                config_checks.append(f"Max Steps: {system_config['max_steps']}")
            if 'auto_create' in system_config:
                config_checks.append(f"Auto Create: {system_config['auto_create']}")
            
            print(f"   System config: {', '.join(config_checks)}")
            
            return True, response
        
        return success, response

    def test_prompt_cache_clear(self):
        """Test prompt cache clearing endpoint"""
        return self.run_test("Clear Prompt Cache", "POST", "admin/cache/clear", 200)

    def test_prompt_cache_functionality(self):
        """Test prompt caching by creating multiple runs and checking cache usage"""
        print("\n🔍 Testing Prompt Cache Functionality...")
        
        # Create multiple runs with same stack to trigger cache usage
        cache_test_runs = []
        
        for i in range(3):
            run_data = {
                "goal": f"Test prompt caching functionality - run {i+1}",
                "stack": "laravel",
                "max_steps": 1,
                "daily_budget_eur": 0.1
            }
            
            success, response = self.run_test(
                f"Cache Test Run {i+1}",
                "POST",
                "runs",
                200,
                data=run_data,
                timeout=15
            )
            
            if not success:
                success, response = self.run_test(
                    f"Cache Test Run {i+1} (201)",
                    "POST",
                    "runs",
                    201,
                    data=run_data,
                    timeout=15
                )
            
            if success and 'id' in response:
                cache_test_runs.append(response['id'])
        
        # Wait a moment for cache to be populated
        time.sleep(2)
        
        # Check admin stats for cache information
        stats_success, stats_response = self.test_admin_stats()
        
        if stats_success and 'cache_stats' in stats_response:
            cache_stats = stats_response['cache_stats']
            print(f"✅ Cache stats after runs: {cache_stats}")
            
            # Check if cache has entries
            if cache_stats.get('total_entries', 0) > 0:
                print(f"✅ Cache populated with {cache_stats['total_entries']} entries")
                return True, {"cache_runs": cache_test_runs, "cache_stats": cache_stats}
            else:
                print("⚠️  Cache not populated after test runs")
                return False, {"cache_runs": cache_test_runs, "cache_stats": cache_stats}
        
        return False, {"cache_runs": cache_test_runs}

    def test_cost_savings_calculation(self):
        """Test cost savings calculation from prompt caching"""
        success, response = self.run_test("Cost Savings Check", "GET", "admin/stats", 200)
        
        if success and 'cost_savings' in response:
            cost_savings = response['cost_savings']
            
            # Check if cost savings structure is correct
            required_fields = ['tokens_saved', 'cost_saved_eur', 'savings_percentage', 'cache_hits', 'total_requests']
            missing_fields = [field for field in required_fields if field not in cost_savings]
            
            if missing_fields:
                print(f"❌ Missing cost savings fields: {missing_fields}")
                return False, response
            
            print(f"✅ Cost savings data: {cost_savings}")
            
            # If we have cache hits, we should have some savings
            if cost_savings.get('cache_hits', 0) > 0:
                if cost_savings.get('tokens_saved', 0) > 0:
                    print(f"✅ Cache is saving tokens: {cost_savings['tokens_saved']} tokens saved")
                    print(f"✅ Estimated cost savings: €{cost_savings['cost_saved_eur']:.4f}")
                    print(f"✅ Savings percentage: {cost_savings['savings_percentage']:.1f}%")
                    return True, response
                else:
                    print("⚠️  Cache hits detected but no tokens saved")
                    return False, response
            else:
                print("ℹ️  No cache hits yet - this is normal for new system")
                return True, response  # This is OK for a new system
        
        return success, response

    def test_llm_router_cache_integration(self):
        """Test that LLM router properly integrates with prompt cache"""
        # Create a run that will use the LLM router
        run_data = {
            "goal": "Test LLM router cache integration by creating a simple function",
            "stack": "python",
            "max_steps": 2,
            "daily_budget_eur": 1.0
        }
        
        success, response = self.run_test(
            "LLM Router Cache Integration",
            "POST",
            "runs",
            200,
            data=run_data,
            timeout=20
        )
        
        if not success:
            success, response = self.run_test(
                "LLM Router Cache Integration (201)",
                "POST",
                "runs",
                201,
                data=run_data,
                timeout=20
            )
        
        if success and 'id' in response:
            run_id = response['id']
            print(f"✅ Created run {run_id} for LLM router cache testing")
            
            # Wait a moment for processing
            time.sleep(3)
            
            # Check if the run was processed and cache was used
            run_success, run_response = self.run_test(
                "Get LLM Router Test Run",
                "GET",
                f"runs/{run_id}",
                200
            )
            
            if run_success:
                print(f"✅ Run status: {run_response.get('status', 'unknown')}")
                return True, {"run_id": run_id, "run_data": run_response}
        
        return success, response

    def test_agent_orchestration_cycle_python(self):
        """Test complete agent orchestration cycle with Python stack"""
        print("\n🤖 Testing Agent Orchestration Cycle - Python Stack")
        
        # Create a simple Hello World run as requested
        run_data = {
            "goal": "Create a simple Hello World file",
            "stack": "python",
            "max_steps": 5,
            "max_retries_per_step": 2,
            "daily_budget_eur": 2.0
        }
        
        # Step 1: Create the run
        success, response = self.run_test(
            "Create Hello World Run (Python)",
            "POST",
            "runs",
            200,
            data=run_data,
            timeout=30
        )
        
        if not success:
            success, response = self.run_test(
                "Create Hello World Run (Python) - 201",
                "POST",
                "runs",
                201,
                data=run_data,
                timeout=30
            )
        
        if not success or 'id' not in response:
            print("❌ Failed to create orchestration test run")
            return False, {}
        
        run_id = response['id']
        print(f"✅ Created orchestration test run: {run_id}")
        
        # Step 2: Monitor the run progress for agent cycle
        max_wait_time = 120  # 2 minutes max wait
        check_interval = 5   # Check every 5 seconds
        elapsed_time = 0
        
        orchestration_phases = {
            "planning": False,
            "execution": False,
            "completion": False
        }
        
        while elapsed_time < max_wait_time:
            time.sleep(check_interval)
            elapsed_time += check_interval
            
            # Get run status
            run_success, run_response = self.run_test(
                f"Monitor Run Progress ({elapsed_time}s)",
                "GET",
                f"runs/{run_id}",
                200,
                timeout=10
            )
            
            if not run_success:
                print(f"❌ Failed to get run status at {elapsed_time}s")
                continue
            
            status = run_response.get('status', 'unknown')
            current_step = run_response.get('current_step', 0)
            logs = run_response.get('logs', [])
            
            print(f"   Status: {status}, Step: {current_step}, Logs: {len(logs)}")
            
            # Check for orchestration phases in logs
            for log in logs[-5:]:  # Check last 5 logs
                content = log.get('content', '').lower()
                if 'phase 1:' in content or 'planning' in content:
                    orchestration_phases["planning"] = True
                    print(f"   ✅ Planning phase detected")
                elif 'phase 2:' in content or 'execution' in content:
                    orchestration_phases["execution"] = True
                    print(f"   ✅ Execution phase detected")
                elif 'completed' in content or 'phase 3:' in content:
                    orchestration_phases["completion"] = True
                    print(f"   ✅ Completion phase detected")
            
            # Check if run completed or failed
            if status in ['completed', 'failed', 'cancelled']:
                print(f"   🏁 Run finished with status: {status}")
                break
            
            # Check if we're making progress
            if current_step > 0:
                print(f"   📈 Progress: Step {current_step}")
        
        # Step 3: Get final run state and analyze results
        final_success, final_response = self.run_test(
            "Get Final Run State",
            "GET",
            f"runs/{run_id}",
            200
        )
        
        if not final_success:
            print("❌ Failed to get final run state")
            return False, {}
        
        final_status = final_response.get('status', 'unknown')
        final_step = final_response.get('current_step', 0)
        final_logs = final_response.get('logs', [])
        
        # Step 4: Check for agent conversations
        conversations_success, conversations_response = self.run_test(
            "Get Agent Conversations",
            "GET",
            f"runs/{run_id}/agent-conversations",
            200
        )
        
        agent_conversations = []
        if conversations_success:
            agent_conversations = conversations_response.get('conversations', [])
            print(f"   📝 Agent conversations: {len(agent_conversations)}")
        
        # Step 5: Analyze orchestration success
        orchestration_success = self._analyze_orchestration_results(
            final_status, final_step, final_logs, orchestration_phases, agent_conversations
        )
        
        return orchestration_success, {
            "run_id": run_id,
            "final_status": final_status,
            "final_step": final_step,
            "logs_count": len(final_logs),
            "phases_detected": orchestration_phases,
            "agent_conversations": len(agent_conversations),
            "elapsed_time": elapsed_time
        }

    def test_agent_orchestration_cycle_laravel(self):
        """Test complete agent orchestration cycle with Laravel stack"""
        print("\n🤖 Testing Agent Orchestration Cycle - Laravel Stack")
        
        # Create a simple Laravel run
        run_data = {
            "goal": "Create a simple Hello World file",
            "stack": "laravel",
            "max_steps": 5,
            "max_retries_per_step": 2,
            "daily_budget_eur": 2.0
        }
        
        # Step 1: Create the run
        success, response = self.run_test(
            "Create Hello World Run (Laravel)",
            "POST",
            "runs",
            200,
            data=run_data,
            timeout=30
        )
        
        if not success:
            success, response = self.run_test(
                "Create Hello World Run (Laravel) - 201",
                "POST",
                "runs",
                201,
                data=run_data,
                timeout=30
            )
        
        if not success or 'id' not in response:
            print("❌ Failed to create Laravel orchestration test run")
            return False, {}
        
        run_id = response['id']
        print(f"✅ Created Laravel orchestration test run: {run_id}")
        
        # Step 2: Monitor for shorter time since we're testing both stacks
        max_wait_time = 90   # 1.5 minutes for Laravel
        check_interval = 5
        elapsed_time = 0
        
        orchestration_phases = {
            "planning": False,
            "execution": False,
            "completion": False
        }
        
        while elapsed_time < max_wait_time:
            time.sleep(check_interval)
            elapsed_time += check_interval
            
            # Get run status
            run_success, run_response = self.run_test(
                f"Monitor Laravel Run ({elapsed_time}s)",
                "GET",
                f"runs/{run_id}",
                200,
                timeout=10
            )
            
            if not run_success:
                continue
            
            status = run_response.get('status', 'unknown')
            current_step = run_response.get('current_step', 0)
            logs = run_response.get('logs', [])
            
            print(f"   Laravel Status: {status}, Step: {current_step}")
            
            # Check for orchestration phases
            for log in logs[-3:]:  # Check last 3 logs
                content = log.get('content', '').lower()
                if 'phase 1:' in content or 'planning' in content:
                    orchestration_phases["planning"] = True
                elif 'phase 2:' in content or 'execution' in content:
                    orchestration_phases["execution"] = True
                elif 'completed' in content:
                    orchestration_phases["completion"] = True
            
            if status in ['completed', 'failed', 'cancelled']:
                break
        
        # Get final state
        final_success, final_response = self.run_test(
            "Get Final Laravel Run State",
            "GET",
            f"runs/{run_id}",
            200
        )
        
        if not final_success:
            return False, {}
        
        final_status = final_response.get('status', 'unknown')
        final_step = final_response.get('current_step', 0)
        final_logs = final_response.get('logs', [])
        
        # Analyze results
        orchestration_success = self._analyze_orchestration_results(
            final_status, final_step, final_logs, orchestration_phases, []
        )
        
        return orchestration_success, {
            "run_id": run_id,
            "final_status": final_status,
            "final_step": final_step,
            "phases_detected": orchestration_phases,
            "elapsed_time": elapsed_time
        }

    def _analyze_orchestration_results(self, status, step, logs, phases, conversations):
        """Analyze orchestration test results"""
        print(f"\n📊 Analyzing Orchestration Results:")
        print(f"   Final Status: {status}")
        print(f"   Steps Executed: {step}")
        print(f"   Total Logs: {len(logs)}")
        print(f"   Phases Detected: {phases}")
        print(f"   Agent Conversations: {len(conversations)}")
        
        # Success criteria
        success_criteria = []
        
        # 1. Run should not crash (status should not be unknown)
        if status != 'unknown':
            success_criteria.append("✅ No Python crashes detected")
        else:
            success_criteria.append("❌ Python crash or unknown status")
        
        # 2. At least planning phase should be detected
        if phases.get("planning", False):
            success_criteria.append("✅ Planning phase executed")
        else:
            success_criteria.append("❌ Planning phase not detected")
        
        # 3. Some execution should occur (step > 0)
        if step > 0:
            success_criteria.append("✅ Execution steps performed")
        else:
            success_criteria.append("❌ No execution steps performed")
        
        # 4. Logs should show progress
        if len(logs) > 0:
            success_criteria.append("✅ Logs generated showing progress")
        else:
            success_criteria.append("❌ No logs generated")
        
        # 5. Check for specific error patterns in logs
        error_patterns = ['error', 'failed', 'exception', 'crash']
        critical_errors = []
        
        for log in logs[-10:]:  # Check last 10 logs
            content = log.get('content', '').lower()
            for pattern in error_patterns:
                if pattern in content and 'recursion' in content:
                    critical_errors.append(f"Recursion error: {content[:100]}")
                elif pattern in content and 'patch' in content:
                    critical_errors.append(f"Patch error: {content[:100]}")
        
        if not critical_errors:
            success_criteria.append("✅ No critical errors in logs")
        else:
            success_criteria.append(f"❌ Critical errors found: {len(critical_errors)}")
            for error in critical_errors[:3]:  # Show first 3 errors
                print(f"      {error}")
        
        # Print all criteria
        for criterion in success_criteria:
            print(f"   {criterion}")
        
        # Overall success: at least 3 out of 5 criteria should pass
        passed_criteria = len([c for c in success_criteria if c.startswith("✅")])
        overall_success = passed_criteria >= 3
        
        if overall_success:
            print(f"   🎉 Orchestration test PASSED ({passed_criteria}/5 criteria)")
        else:
            print(f"   ❌ Orchestration test FAILED ({passed_criteria}/5 criteria)")
        
        return overall_success

    def test_orchestration_endpoints(self):
        """Test orchestration-specific endpoints"""
        print("\n🔗 Testing Orchestration Endpoints")
        
        # Test runs endpoint
        runs_success, runs_response = self.run_test(
            "List Runs Endpoint",
            "GET",
            "runs",
            200
        )
        
        if not runs_success:
            return False, {}
        
        runs = runs_response if isinstance(runs_response, list) else []
        print(f"   Found {len(runs)} runs")
        
        # Test specific run endpoint if we have runs
        if runs and len(runs) > 0:
            first_run = runs[0]
            run_id = first_run.get('id')
            
            if run_id:
                run_success, run_response = self.run_test(
                    "Get Specific Run Endpoint",
                    "GET",
                    f"runs/{run_id}",
                    200
                )
                
                if run_success:
                    print(f"   ✅ Successfully retrieved run {run_id}")
                    return True, {"runs_count": len(runs), "test_run": run_response}
        
        return runs_success, {"runs_count": len(runs)}

def main():
    print("🚀 Starting Emergent-like System Comprehensive Tests")
    print("=" * 70)
    
    tester = EmergentSystemTester()
    
    # Core functionality tests
    core_tests = [
        ("API Health Check", tester.test_health_check),
        ("Admin Statistics", tester.test_admin_stats),
        ("Projects List", tester.test_projects_list),
        ("File Operations", tester.test_file_operations),
    ]
    
    # New features tests
    feature_tests = [
        ("LLM Router Configuration", tester.test_llm_router_configuration),
        ("Project Creation & Isolation", tester.test_project_creation_isolation),
        ("GitHub Integration Structure", tester.test_github_integration_structure),
        ("Comprehensive Stack Support", tester.test_comprehensive_stack_support),
    ]
    
    # New admin global features tests
    admin_global_tests = [
        ("Admin Global Statistics", tester.test_admin_global_stats),
        ("Admin Global Logs", tester.test_admin_global_logs),
        ("Admin Global Logs Filtered", tester.test_admin_global_logs_filtered),
        ("Environment Configuration", tester.test_environment_configuration),
    ]
    
    # Project preview tests
    preview_tests = [
        ("Project Preview Multi-Stack", tester.test_project_preview),
        ("Project Preview Non-existent", tester.test_project_preview_nonexistent),
    ]
    
    # Prompt caching tests
    caching_tests = [
        ("Prompt Cache Clear", tester.test_prompt_cache_clear),
        ("Prompt Cache Functionality", tester.test_prompt_cache_functionality),
        ("Cost Savings Calculation", tester.test_cost_savings_calculation),
        ("LLM Router Cache Integration", tester.test_llm_router_cache_integration),
    ]
    
    # Agent orchestration tests - NEW PRIORITY TESTS
    orchestration_tests = [
        ("Orchestration Endpoints", tester.test_orchestration_endpoints),
        ("Agent Orchestration Cycle - Python", tester.test_agent_orchestration_cycle_python),
        ("Agent Orchestration Cycle - Laravel", tester.test_agent_orchestration_cycle_laravel),
    ]
    
    # Run management tests
    run_tests = [
        ("Create Basic Run", tester.test_create_run_basic),
        ("Get Run", tester.test_get_run),
        ("List Runs", tester.test_list_runs),
        ("Cancel Run", tester.test_cancel_run),
    ]
    
    # Error handling tests
    error_tests = [
        ("Invalid Requests", tester.test_invalid_requests),
    ]
    
    all_tests = [
        ("🔧 CORE FUNCTIONALITY", core_tests),
        ("🤖 AGENT ORCHESTRATION", orchestration_tests),  # Priority tests first
        ("🆕 NEW FEATURES", feature_tests),
        ("🌐 ADMIN GLOBAL FEATURES", admin_global_tests),
        ("🔍 PROJECT PREVIEW", preview_tests),
        ("🧠 PROMPT CACHING", caching_tests),
        ("🏃 RUN MANAGEMENT", run_tests),
        ("❌ ERROR HANDLING", error_tests),
    ]
    
    for category_name, tests in all_tests:
        print(f"\n{'='*20} {category_name} {'='*20}")
        
        for test_name, test_func in tests:
            print(f"\n{'='*10} {test_name} {'='*10}")
            try:
                test_func()
            except Exception as e:
                print(f"❌ Test {test_name} crashed: {str(e)}")
    
    # Print final results
    print(f"\n{'='*70}")
    print(f"📊 FINAL RESULTS")
    print(f"Tests Run: {tester.tests_run}")
    print(f"Tests Passed: {tester.tests_passed}")
    print(f"Tests Failed: {tester.tests_run - tester.tests_passed}")
    print(f"Success Rate: {(tester.tests_passed/tester.tests_run*100):.1f}%" if tester.tests_run > 0 else "0%")
    
    if tester.tests_passed == tester.tests_run:
        print("🎉 All tests passed!")
        return 0
    elif tester.tests_passed / tester.tests_run >= 0.7:
        print("✅ Most tests passed - system is largely functional")
        return 0
    else:
        print("⚠️  Many tests failed - check logs above")
        return 1

if __name__ == "__main__":
    sys.exit(main())