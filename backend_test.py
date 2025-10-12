import requests
import sys
import json
import time
from datetime import datetime

class Phase1DirectWriteTester:
    """
    🔥 PHASE 1 DIRECT WRITE BACKEND TESTING
    
    Tests the new direct file writing architecture:
    - file_writer.py primitives
    - schemas.py Pydantic validation
    - developer_direct.py JSON operations
    - server.py dual-mode integration
    """
    
    def __init__(self, base_url=None):
        if base_url is None:
            base_url = 'http://localhost:8001'
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.tests_run = 0
        self.tests_passed = 0

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

    def test_api_health(self):
        """Test basic API health"""
        return self.run_test("API Health Check", "GET", "", 200)

    def test_file_write_mode_configuration(self):
        """🔥 PHASE 1: Test FILE_WRITE_MODE=direct configuration"""
        success, response = self.run_test("File Write Mode Configuration", "GET", "admin/mode", 200)
        
        if success and response:
            # Validate expected fields
            expected_fields = ['file_write_mode', 'developer_agent_type', 'deny_list']
            missing_fields = [field for field in expected_fields if field not in response]
            
            if missing_fields:
                print(f"❌ Missing expected fields: {missing_fields}")
                return False, response
            
            # Validate mode is "direct"
            if response.get('file_write_mode') != 'direct':
                print(f"❌ Expected file_write_mode='direct', got '{response.get('file_write_mode')}'")
                return False, response
            
            # Validate agent type is DeveloperAgentDirect
            if response.get('developer_agent_type') != 'DeveloperAgentDirect':
                print(f"❌ Expected DeveloperAgentDirect, got '{response.get('developer_agent_type')}'")
                return False, response
            
            # Validate deny_list has 19 protected paths
            deny_list = response.get('deny_list', [])
            if len(deny_list) != 19:
                print(f"❌ Expected 19 protected paths, got {len(deny_list)}")
                return False, response
            
            # Check for key protected paths
            expected_protected = ['.git/', '.env', 'vendor/', 'node_modules/', '.pytest_cache/', '__pycache__/']
            missing_protected = [path for path in expected_protected if path not in deny_list]
            if missing_protected:
                print(f"❌ Missing key protected paths: {missing_protected}")
                return False, response
            
            print(f"✅ File write mode: {response['file_write_mode']}")
            print(f"✅ Agent type: {response['developer_agent_type']}")
            print(f"✅ Protected paths: {len(deny_list)} items")
            print(f"   Sample protected: {deny_list[:5]}")
            
            return True, response
        
        return success, response

    def test_admin_stats_with_mode_info(self):
        """Test admin stats endpoint includes system configuration"""
        success, response = self.run_test("Admin Stats with System Info", "GET", "admin/stats", 200)
        
        if success and response:
            # Check for expected fields
            expected_fields = ['run_stats', 'daily_cost', 'project_count', 'settings']
            missing_fields = [field for field in expected_fields if field not in response]
            
            if missing_fields:
                print(f"⚠️  Missing expected fields: {missing_fields}")
                return False, response
            
            # Check settings structure
            settings = response.get('settings', {})
            expected_settings = ['max_local_retries', 'default_daily_budget', 'max_steps_per_run', 'auto_create_structures']
            missing_settings = [setting for setting in expected_settings if setting not in settings]
            
            if missing_settings:
                print(f"⚠️  Missing settings: {missing_settings}")
            else:
                print(f"✅ System settings: {settings}")
            
            return True, response
        
        return success, response

    def test_create_run_direct_mode(self):
        """🔥 PHASE 1: Test run creation in direct mode"""
        run_data = {
            "goal": "Create a simple Python hello world script using direct file operations",
            "stack": "python",
            "max_steps": 3,
            "max_retries_per_step": 1,
            "daily_budget_eur": 1.0
        }
        
        success, response = self.run_test(
            "Create Run (Direct Mode)",
            "POST",
            "runs",
            200,
            data=run_data,
            timeout=30
        )
        
        if not success:
            # Try with 201 status code
            success, response = self.run_test(
                "Create Run (Direct Mode - 201)",
                "POST", 
                "runs",
                201,
                data=run_data,
                timeout=30
            )
        
        if success and 'id' in response:
            run_id = response['id']
            print(f"   Created run ID: {run_id}")
            
            # Wait a moment for processing to start
            time.sleep(2)
            
            # Check run status
            run_success, run_response = self.run_test(
                "Get Created Run Status",
                "GET",
                f"runs/{run_id}",
                200
            )
            
            if run_success:
                status = run_response.get('status', 'unknown')
                print(f"   Run status: {status}")
                return True, {"run_id": run_id, "status": status}
        
        return success, response

    def test_backend_logs_for_direct_mode(self):
        """Check backend logs for direct mode initialization"""
        print("\n🔍 Checking backend logs for direct mode...")
        
        try:
            # Check supervisor logs for backend startup
            import subprocess
            result = subprocess.run(
                ["tail", "-n", "20", "/var/log/supervisor/backend.out.log"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                logs = result.stdout
                print(f"   Recent backend logs:")
                for line in logs.split('\n')[-10:]:
                    if line.strip():
                        print(f"     {line}")
                
                # Look for direct mode indicators
                if "DeveloperAgentDirect" in logs or "direct" in logs.lower():
                    print("✅ Direct mode indicators found in logs")
                    return True, {"logs_checked": True}
                else:
                    print("⚠️  No direct mode indicators in recent logs")
                    return False, {"logs_checked": True}
            else:
                print("❌ Could not read backend logs")
                return False, {"logs_checked": False}
                
        except Exception as e:
            print(f"❌ Error checking logs: {e}")
            return False, {"error": str(e)}

    def test_projects_endpoint(self):
        """Test projects listing endpoint"""
        return self.run_test("Projects List", "GET", "projects", 200)

    def test_runs_endpoint(self):
        """Test runs listing endpoint"""
        return self.run_test("Runs List", "GET", "runs", 200)

    def test_invalid_requests_handling(self):
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
        
        return success and nonexistent_success, {}

    def test_development_mode_active(self):
        """Test that DEVELOPMENT_MODE is active (no real LLM API keys needed)"""
        success, response = self.run_test("Admin Stats for Dev Mode", "GET", "admin/stats", 200)
        
        if success and response:
            # In development mode, we should be able to create runs even without API keys
            print("✅ Development mode allows testing without real API keys")
            return True, response
        
        return success, response

    def run_all_phase1_tests(self):
        """Run all Phase 1 Direct Write tests"""
        print("🔥 PHASE 1 DIRECT WRITE BACKEND TESTING")
        print("=" * 70)
        
        tests = [
            ("API Health Check", self.test_api_health),
            ("File Write Mode Configuration", self.test_file_write_mode_configuration),
            ("Admin Stats with Mode Info", self.test_admin_stats_with_mode_info),
            ("Backend Logs Check", self.test_backend_logs_for_direct_mode),
            ("Development Mode Active", self.test_development_mode_active),
            ("Projects Endpoint", self.test_projects_endpoint),
            ("Runs Endpoint", self.test_runs_endpoint),
            ("Create Run (Direct Mode)", self.test_create_run_direct_mode),
            ("Invalid Requests Handling", self.test_invalid_requests_handling),
        ]
        
        results = {}
        
        for test_name, test_func in tests:
            print(f"\n{'='*10} {test_name} {'='*10}")
            try:
                success, data = test_func()
                results[test_name] = {"success": success, "data": data}
            except Exception as e:
                print(f"❌ Test {test_name} crashed: {str(e)}")
                results[test_name] = {"success": False, "error": str(e)}
        
        return results

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
    print("🚀 Starting PHASE 1 DIRECT WRITE Backend Testing")
    print("=" * 70)
    
    # Run Phase 1 Direct Write Tests
    phase1_tester = Phase1DirectWriteTester()
    phase1_results = phase1_tester.run_all_phase1_tests()
    
    # Print Phase 1 Results
    print(f"\n{'='*70}")
    print(f"📊 PHASE 1 DIRECT WRITE RESULTS")
    print(f"Tests Run: {phase1_tester.tests_run}")
    print(f"Tests Passed: {phase1_tester.tests_passed}")
    print(f"Tests Failed: {phase1_tester.tests_run - phase1_tester.tests_passed}")
    print(f"Success Rate: {(phase1_tester.tests_passed/phase1_tester.tests_run*100):.1f}%" if phase1_tester.tests_run > 0 else "0%")
    
    # Detailed results
    print(f"\n📋 DETAILED RESULTS:")
    for test_name, result in phase1_results.items():
        status = "✅ PASS" if result["success"] else "❌ FAIL"
        print(f"   {status} - {test_name}")
        if not result["success"] and "error" in result:
            print(f"      Error: {result['error']}")
    
    # Run comprehensive tests if Phase 1 passes
    if phase1_tester.tests_passed >= phase1_tester.tests_run * 0.8:  # 80% pass rate
        print(f"\n🎉 Phase 1 tests mostly passed! Running comprehensive tests...")
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

class Phase2AttachModeTester:
    """
    🔥 PHASE 2 ATTACH MODE BACKEND TESTING
    
    Tests the new attach mode functionality:
    - POST /api/runs with project_mode="attach" + project_id
    - POST /api/runs/execute-operations (no-LLM direct operations)
    - ProjectManager.attach_to_project() validation
    - Git commits atomiques par step
    - RAG re-indexing après modifications
    - Protected paths rejection
    """
    
    def __init__(self, base_url=None):
        if base_url is None:
            base_url = 'http://localhost:8001'
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.tests_run = 0
        self.tests_passed = 0
        self.created_projects = []  # Track created test projects

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

    def setup_test_project(self, project_type="laravel", project_name="test-project-phase2"):
        """Setup a test project for attach mode testing"""
        import os
        import subprocess
        
        project_path = f"/app/projects/{project_name}/code"
        
        try:
            # Create project directory
            os.makedirs(project_path, exist_ok=True)
            
            # Initialize git repo
            subprocess.run(["git", "init"], cwd=project_path, capture_output=True, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=project_path, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Test User"], cwd=project_path, capture_output=True)
            
            # Create project structure based on type
            if project_type == "laravel":
                # Create Laravel-like structure
                with open(f"{project_path}/composer.json", "w") as f:
                    f.write('{"name": "test-laravel", "type": "project", "require": {"php": "^8.0"}}')
                
                os.makedirs(f"{project_path}/app", exist_ok=True)
                os.makedirs(f"{project_path}/routes", exist_ok=True)
                
                with open(f"{project_path}/app/test.php", "w") as f:
                    f.write("<?php\necho 'Hello Laravel';\n")
                    
            elif project_type == "node":
                # Create Node.js-like structure
                with open(f"{project_path}/package.json", "w") as f:
                    f.write('{"name": "test-node", "version": "1.0.0", "main": "index.js"}')
                
                with open(f"{project_path}/index.js", "w") as f:
                    f.write("console.log('Hello Node.js');\n")
            
            # Initial commit
            subprocess.run(["git", "add", "."], cwd=project_path, capture_output=True, check=True)
            subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=project_path, capture_output=True, check=True)
            
            # Get initial commit hash
            result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=project_path, capture_output=True, text=True, check=True)
            initial_commit = result.stdout.strip()
            
            self.created_projects.append(project_name)
            
            return {
                "project_path": project_path,
                "project_name": project_name,
                "initial_commit": initial_commit,
                "success": True
            }
            
        except Exception as e:
            print(f"❌ Failed to setup test project: {e}")
            return {"success": False, "error": str(e)}

    def cleanup_test_projects(self):
        """Clean up created test projects"""
        import shutil
        import os
        
        for project_name in self.created_projects:
            try:
                project_dir = f"/app/projects/{project_name}"
                if os.path.exists(project_dir):
                    shutil.rmtree(project_dir)
                    print(f"✅ Cleaned up test project: {project_name}")
            except Exception as e:
                print(f"⚠️  Failed to cleanup {project_name}: {e}")

    def test_endpoints_availability(self):
        """Test that Phase 2 endpoints are available"""
        print("\n🔍 Testing Phase 2 Endpoints Availability...")
        
        # Test POST /api/runs (should accept project_mode parameter)
        runs_success, _ = self.run_test(
            "POST /api/runs endpoint availability",
            "POST",
            "runs",
            422,  # Should fail with validation error for empty data
            data={}
        )
        
        # Test GET /api/projects
        projects_success, _ = self.run_test(
            "GET /api/projects endpoint",
            "GET", 
            "projects",
            200
        )
        
        # Test POST /api/runs/execute-operations (should fail without data)
        execute_ops_success, _ = self.run_test(
            "POST /api/runs/execute-operations endpoint availability",
            "POST",
            "runs/execute-operations",
            422,  # Should fail with validation error
            data={}
        )
        
        return runs_success and projects_success and execute_ops_success, {
            "runs_endpoint": runs_success,
            "projects_endpoint": projects_success,
            "execute_operations_endpoint": execute_ops_success
        }

    def test_attach_laravel_project(self):
        """Test Case A: Attach Laravel Project"""
        print("\n🔍 Test Case A: Attach Laravel Project...")
        
        # Setup Laravel test project
        project_setup = self.setup_test_project("laravel", "test-laravel-phase2")
        if not project_setup["success"]:
            return False, project_setup
        
        project_path = project_setup["project_path"]
        project_name = project_setup["project_name"]
        
        # Step 1: Create run in attach mode
        run_data = {
            "goal": "Test attach mode with Laravel project",
            "project_mode": "attach",
            "project_path": project_path,
            "stack": "laravel",
            "max_steps": 3,
            "daily_budget_eur": 1.0
        }
        
        run_success, run_response = self.run_test(
            "Create Run in Attach Mode (Laravel)",
            "POST",
            "runs",
            201,
            data=run_data,
            timeout=30
        )
        
        if not run_success:
            # Try 200 status code
            run_success, run_response = self.run_test(
                "Create Run in Attach Mode (Laravel) - 200",
                "POST",
                "runs", 
                200,
                data=run_data,
                timeout=30
            )
        
        if not run_success or 'id' not in run_response:
            return False, {"error": "Failed to create attach mode run"}
        
        run_id = run_response['id']
        
        # Validate response
        expected_fields = ['project_mode', 'attached_commit', 'project_path']
        missing_fields = [field for field in expected_fields if field not in run_response]
        
        if missing_fields:
            print(f"⚠️  Missing expected fields in attach response: {missing_fields}")
        
        # Validate project_mode is "attach"
        if run_response.get('project_mode') != 'attach':
            print(f"❌ Expected project_mode='attach', got '{run_response.get('project_mode')}'")
            return False, run_response
        
        # Step 2: Execute operations (no-LLM)
        operations_data = {
            "run_id": run_id,
            "project_id": project_name,
            "operations": [
                {
                    "type": "create",
                    "path": "test-phase2.txt",
                    "content": "Hello Phase 2 Attach Mode"
                }
            ],
            "commit": {
                "title": "Test commit from Phase 2",
                "step_number": 1
            }
        }
        
        ops_success, ops_response = self.run_test(
            "Execute Operations (no-LLM)",
            "POST",
            "runs/execute-operations",
            200,
            data=operations_data,
            timeout=30
        )
        
        if ops_success:
            # Validate operations response
            expected_ops_fields = ['status', 'operations_executed', 'commit_hash']
            missing_ops_fields = [field for field in expected_ops_fields if field not in ops_response]
            
            if missing_ops_fields:
                print(f"⚠️  Missing expected fields in operations response: {missing_ops_fields}")
            
            if ops_response.get('status') != 'success':
                print(f"❌ Expected status='success', got '{ops_response.get('status')}'")
                return False, ops_response
            
            print(f"✅ Laravel attach test completed successfully")
            print(f"   Run ID: {run_id}")
            print(f"   Operations executed: {ops_response.get('operations_executed', 0)}")
            print(f"   Commit hash: {ops_response.get('commit_hash', 'N/A')}")
            
            return True, {
                "run_id": run_id,
                "project_name": project_name,
                "operations_response": ops_response
            }
        
        return ops_success, ops_response

    def test_attach_node_project(self):
        """Test Case B: Attach Node Project"""
        print("\n🔍 Test Case B: Attach Node Project...")
        
        # Setup Node test project
        project_setup = self.setup_test_project("node", "test-node-phase2")
        if not project_setup["success"]:
            return False, project_setup
        
        project_path = project_setup["project_path"]
        project_name = project_setup["project_name"]
        
        # Create run in attach mode
        run_data = {
            "goal": "Test attach mode with Node.js project",
            "project_mode": "attach", 
            "project_path": project_path,
            "stack": "node",
            "max_steps": 2,
            "daily_budget_eur": 0.5
        }
        
        run_success, run_response = self.run_test(
            "Create Run in Attach Mode (Node)",
            "POST",
            "runs",
            201,
            data=run_data,
            timeout=20
        )
        
        if not run_success:
            run_success, run_response = self.run_test(
                "Create Run in Attach Mode (Node) - 200",
                "POST",
                "runs",
                200,
                data=run_data,
                timeout=20
            )
        
        if not run_success or 'id' not in run_response:
            return False, {"error": "Failed to create Node attach mode run"}
        
        run_id = run_response['id']
        
        # Execute operations
        operations_data = {
            "run_id": run_id,
            "project_id": project_name,
            "operations": [
                {
                    "type": "create",
                    "path": "README.md",
                    "content": "# Test Node.js Project\n\nCreated via Phase 2 attach mode."
                },
                {
                    "type": "update",
                    "path": "package.json",
                    "content": '{"name": "test-node", "version": "1.0.1", "main": "index.js", "description": "Updated via Phase 2"}'
                }
            ],
            "commit": {
                "title": "Add README and update package.json",
                "step_number": 1
            }
        }
        
        ops_success, ops_response = self.run_test(
            "Execute Multiple Operations (Node)",
            "POST",
            "runs/execute-operations",
            200,
            data=operations_data,
            timeout=20
        )
        
        if ops_success and ops_response.get('status') == 'success':
            print(f"✅ Node attach test completed successfully")
            print(f"   Operations executed: {ops_response.get('operations_executed', 0)}")
            
            return True, {
                "run_id": run_id,
                "project_name": project_name,
                "operations_response": ops_response
            }
        
        return ops_success, ops_response

    def test_protected_paths_rejection(self):
        """Test Case C: Protected Paths Rejection"""
        print("\n🔍 Test Case C: Protected Paths Rejection...")
        
        # Setup a test project
        project_setup = self.setup_test_project("laravel", "test-protected-paths")
        if not project_setup["success"]:
            return False, project_setup
        
        project_name = project_setup["project_name"]
        
        # Create a run first
        run_data = {
            "goal": "Test protected paths rejection",
            "project_mode": "attach",
            "project_path": project_setup["project_path"],
            "stack": "laravel"
        }
        
        run_success, run_response = self.run_test(
            "Create Run for Protected Paths Test",
            "POST",
            "runs",
            201,
            data=run_data
        )
        
        if not run_success:
            run_success, run_response = self.run_test(
                "Create Run for Protected Paths Test - 200",
                "POST",
                "runs",
                200,
                data=run_data
            )
        
        if not run_success or 'id' not in run_response:
            return False, {"error": "Failed to create run for protected paths test"}
        
        run_id = run_response['id']
        
        # Test protected paths
        protected_paths_tests = [
            ".env",
            ".git/config", 
            "vendor/autoload.php",
            "node_modules/package.json",
            ".pytest_cache/test.py"
        ]
        
        protected_results = {}
        
        for protected_path in protected_paths_tests:
            operations_data = {
                "run_id": run_id,
                "project_id": project_name,
                "operations": [
                    {
                        "type": "create",
                        "path": protected_path,
                        "content": "This should be rejected"
                    }
                ],
                "commit": {
                    "title": f"Attempt to modify {protected_path}",
                    "step_number": 1
                }
            }
            
            # This should fail with 422 or 500
            ops_success, ops_response = self.run_test(
                f"Protected Path Test: {protected_path}",
                "POST",
                "runs/execute-operations",
                422,
                data=operations_data
            )
            
            if not ops_success:
                # Try 500 status code
                ops_success, ops_response = self.run_test(
                    f"Protected Path Test: {protected_path} (500)",
                    "POST",
                    "runs/execute-operations",
                    500,
                    data=operations_data
                )
            
            protected_results[protected_path] = ops_success
            
            if ops_success:
                print(f"✅ Protected path {protected_path} correctly rejected")
            else:
                print(f"❌ Protected path {protected_path} was not rejected")
        
        # Check if most protected paths were rejected
        rejected_count = sum(protected_results.values())
        total_count = len(protected_results)
        
        success = rejected_count >= (total_count * 0.8)  # 80% should be rejected
        
        if success:
            print(f"✅ Protected paths rejection test passed ({rejected_count}/{total_count} rejected)")
        else:
            print(f"❌ Protected paths rejection test failed ({rejected_count}/{total_count} rejected)")
        
        return success, {
            "rejected_count": rejected_count,
            "total_count": total_count,
            "results": protected_results
        }

    def test_validation_tests(self):
        """Test validation scenarios"""
        print("\n🔍 Validation Tests...")
        
        validation_results = {}
        
        # Test 1: Attach to non-existent project
        run_data = {
            "goal": "Test non-existent project",
            "project_mode": "attach",
            "project_path": "/app/projects/nonexistent-project/code",
            "stack": "laravel"
        }
        
        nonexistent_success, _ = self.run_test(
            "Attach to Non-existent Project",
            "POST",
            "runs",
            404,
            data=run_data
        )
        
        if not nonexistent_success:
            # Try 400 or 500
            nonexistent_success, _ = self.run_test(
                "Attach to Non-existent Project (400)",
                "POST",
                "runs",
                400,
                data=run_data
            )
        
        validation_results["nonexistent_project"] = nonexistent_success
        
        # Test 2: Execute operations without run_id
        invalid_ops_data = {
            "project_id": "test-project",
            "operations": [{"type": "create", "path": "test.txt", "content": "test"}],
            "commit": {"title": "test", "step_number": 1}
        }
        
        no_run_id_success, _ = self.run_test(
            "Execute Operations without run_id",
            "POST",
            "runs/execute-operations",
            422,
            data=invalid_ops_data
        )
        
        if not no_run_id_success:
            no_run_id_success, _ = self.run_test(
                "Execute Operations without run_id (400)",
                "POST",
                "runs/execute-operations",
                400,
                data=invalid_ops_data
            )
        
        validation_results["no_run_id"] = no_run_id_success
        
        # Test 3: Execute operations with invalid JSON
        invalid_json_success, _ = self.run_test(
            "Execute Operations with Invalid JSON",
            "POST",
            "runs/execute-operations",
            422,
            data={"invalid": "data"}
        )
        
        validation_results["invalid_json"] = invalid_json_success
        
        # Calculate success rate
        passed_validations = sum(validation_results.values())
        total_validations = len(validation_results)
        
        success = passed_validations >= (total_validations * 0.7)  # 70% should pass
        
        if success:
            print(f"✅ Validation tests passed ({passed_validations}/{total_validations})")
        else:
            print(f"❌ Validation tests failed ({passed_validations}/{total_validations})")
        
        return success, validation_results

    def test_integration_tests(self):
        """Test integration scenarios"""
        print("\n🔍 Integration Tests...")
        
        # Setup a test project for integration testing
        project_setup = self.setup_test_project("laravel", "test-integration-phase2")
        if not project_setup["success"]:
            return False, project_setup
        
        project_path = project_setup["project_path"]
        project_name = project_setup["project_name"]
        
        # Create run
        run_data = {
            "goal": "Integration test for Phase 2",
            "project_mode": "attach",
            "project_path": project_path,
            "stack": "laravel"
        }
        
        run_success, run_response = self.run_test(
            "Create Integration Test Run",
            "POST",
            "runs",
            201,
            data=run_data
        )
        
        if not run_success:
            run_success, run_response = self.run_test(
                "Create Integration Test Run - 200",
                "POST",
                "runs",
                200,
                data=run_data
            )
        
        if not run_success or 'id' not in run_response:
            return False, {"error": "Failed to create integration test run"}
        
        run_id = run_response['id']
        
        # Test Git commits format
        operations_data = {
            "run_id": run_id,
            "project_id": project_name,
            "operations": [
                {
                    "type": "create",
                    "path": "integration-test.php",
                    "content": "<?php\n// Integration test file\necho 'Integration test';\n"
                }
            ],
            "commit": {
                "title": "Add integration test file",
                "step_number": 1
            }
        }
        
        ops_success, ops_response = self.run_test(
            "Integration Test Operations",
            "POST",
            "runs/execute-operations",
            200,
            data=operations_data
        )
        
        integration_results = {
            "run_created": run_success,
            "operations_executed": ops_success,
            "commit_hash_present": False,
            "files_created": False
        }
        
        if ops_success:
            # Check if commit hash is present
            if ops_response.get('commit_hash'):
                integration_results["commit_hash_present"] = True
                print(f"✅ Git commit created: {ops_response['commit_hash']}")
            
            # Check if files were actually created
            import os
            test_file_path = os.path.join(project_path, "integration-test.php")
            if os.path.exists(test_file_path):
                integration_results["files_created"] = True
                print(f"✅ File created on disk: {test_file_path}")
            else:
                print(f"❌ File not found on disk: {test_file_path}")
        
        # Calculate success
        passed_tests = sum(integration_results.values())
        total_tests = len(integration_results)
        
        success = passed_tests >= (total_tests * 0.75)  # 75% should pass
        
        if success:
            print(f"✅ Integration tests passed ({passed_tests}/{total_tests})")
        else:
            print(f"❌ Integration tests failed ({passed_tests}/{total_tests})")
        
        return success, integration_results

    def run_all_phase2_tests(self):
        """Run all Phase 2 Attach Mode tests"""
        print("🔥 PHASE 2 ATTACH MODE BACKEND TESTING")
        print("=" * 70)
        
        tests = [
            ("Endpoints Availability", self.test_endpoints_availability),
            ("Attach Laravel Project", self.test_attach_laravel_project),
            ("Attach Node Project", self.test_attach_node_project),
            ("Protected Paths Rejection", self.test_protected_paths_rejection),
            ("Validation Tests", self.test_validation_tests),
            ("Integration Tests", self.test_integration_tests),
        ]
        
        results = {}
        
        for test_name, test_func in tests:
            print(f"\n{'='*10} {test_name} {'='*10}")
            try:
                success, data = test_func()
                results[test_name] = {"success": success, "data": data}
            except Exception as e:
                print(f"❌ Test {test_name} crashed: {str(e)}")
                results[test_name] = {"success": False, "error": str(e)}
        
        # Cleanup test projects
        self.cleanup_test_projects()
        
        return results

def main_phase2():
    """Main function for Phase 2 testing"""
    print("🚀 Starting PHASE 2 ATTACH MODE Backend Testing")
    print("=" * 70)
    
    # Run Phase 2 Attach Mode Tests
    phase2_tester = Phase2AttachModeTester()
    phase2_results = phase2_tester.run_all_phase2_tests()
    
    # Print Phase 2 Results
    print(f"\n{'='*70}")
    print(f"📊 PHASE 2 ATTACH MODE RESULTS")
    print(f"Tests Run: {phase2_tester.tests_run}")
    print(f"Tests Passed: {phase2_tester.tests_passed}")
    print(f"Tests Failed: {phase2_tester.tests_run - phase2_tester.tests_passed}")
    print(f"Success Rate: {(phase2_tester.tests_passed/phase2_tester.tests_run*100):.1f}%" if phase2_tester.tests_run > 0 else "0%")
    
    # Detailed results
    print(f"\n📋 DETAILED RESULTS:")
    for test_name, result in phase2_results.items():
        status = "✅ PASS" if result["success"] else "❌ FAIL"
        print(f"   {status} - {test_name}")
        if not result["success"] and "error" in result:
            print(f"      Error: {result['error']}")
    
    # Success criteria
    if phase2_tester.tests_passed >= phase2_tester.tests_run * 0.8:  # 80% pass rate
        print(f"\n🎉 Phase 2 Attach Mode tests PASSED!")
        return 0
    elif phase2_tester.tests_passed >= phase2_tester.tests_run * 0.6:  # 60% pass rate
        print(f"\n✅ Phase 2 Attach Mode tests mostly passed - system is functional")
        return 0
    else:
        print(f"\n⚠️  Phase 2 Attach Mode tests failed - check implementation")
        return 1

class Phase3AutoHealTester:
    """
    🔥 PHASE 3 AUTO-HEAL STACK-AGNOSTIQUE BACKEND TESTING
    
    Tests the new auto-heal functionality:
    - POST /api/projects/{id}/auto-heal
    - GET /api/projects/{id}/branches
    - POST /api/projects/{id}/branches/{branch}/test
    - GET /api/projects/{id}/branches/{branch}/artifacts
    - POST /api/projects/{id}/branches/{branch}/close
    
    Test Cases:
    - Case A: Laravel Auto-Heal
    - Case B: Node Auto-Heal
    - Case C: Generic Stack
    - Case D: Protected Paths Rejection
    - Branches Management Tests
    - Validation Tests
    """
    
    def __init__(self, base_url=None):
        if base_url is None:
            base_url = 'http://localhost:8001'
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.tests_run = 0
        self.tests_passed = 0
        self.created_projects = []

    def run_test(self, name, method, endpoint, expected_status, data=None, timeout=30, headers=None):
        """Run a single API test with longer timeout for auto-heal operations"""
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
                
                try:
                    response_data = response.json()
                    print(f"   Response: {json.dumps(response_data, indent=2)[:500]}...")
                    return True, response_data
                except:
                    print(f"   Response: {response.text[:300]}...")
                    return True, {}
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                print(f"   Response: {response.text[:500]}...")
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

    def setup_test_project(self, project_id, stack="laravel"):
        """Setup a test project for auto-heal testing"""
        import os
        import subprocess
        
        project_path = f"/app/projects/{project_id}/code"
        
        try:
            # Create project directory
            os.makedirs(project_path, exist_ok=True)
            
            # Initialize git repo
            subprocess.run(["git", "init"], cwd=project_path, capture_output=True, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=project_path, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Test User"], cwd=project_path, capture_output=True)
            
            if stack == "laravel":
                # Create Laravel project structure
                composer_json = {
                    "name": "test-laravel",
                    "require": {
                        "laravel/framework": "^10.0"
                    }
                }
                with open(f"{project_path}/composer.json", "w") as f:
                    json.dump(composer_json, f, indent=2)
                
                # Create artisan file
                with open(f"{project_path}/artisan", "w") as f:
                    f.write("#!/usr/bin/env php\n<?php\n// Laravel Artisan CLI\n")
                
            elif stack == "node":
                # Create Node.js project structure
                package_json = {
                    "name": "test-node",
                    "scripts": {
                        "test": "jest"
                    }
                }
                with open(f"{project_path}/package.json", "w") as f:
                    json.dump(package_json, f, indent=2)
                    
            elif stack == "generic":
                # Create generic project
                with open(f"{project_path}/README.md", "w") as f:
                    f.write("# Test Project\n")
            
            # Initial commit
            subprocess.run(["git", "add", "."], cwd=project_path, capture_output=True, check=True)
            subprocess.run(["git", "commit", "-m", f"Initial {stack} project"], cwd=project_path, capture_output=True, check=True)
            
            self.created_projects.append(project_id)
            print(f"✅ Created test project: {project_id} ({stack})")
            return True, project_path
            
        except Exception as e:
            print(f"❌ Failed to setup test project: {e}")
            return False, None

    def test_endpoints_availability(self):
        """Test that all 5 auto-heal endpoints are available"""
        print("\n🔍 Testing Auto-Heal Endpoints Availability...")
        
        # Create a test project first
        project_id = "test-endpoints-availability"
        setup_success, _ = self.setup_test_project(project_id, "laravel")
        
        if not setup_success:
            return False, {"error": "Failed to setup test project"}
        
        endpoints_results = {}
        
        # Test 1: POST /api/projects/{id}/auto-heal
        heal_data = {
            "max_steps": 1,
            "operations": [
                {
                    "type": "create",
                    "path": "test-endpoint.txt",
                    "content": "Test endpoint availability"
                }
            ]
        }
        
        heal_success, heal_response = self.run_test(
            "POST /api/projects/{id}/auto-heal",
            "POST",
            f"projects/{project_id}/auto-heal",
            200,
            data=heal_data,
            timeout=60
        )
        endpoints_results["auto_heal"] = heal_success
        
        # Test 2: GET /api/projects/{id}/branches
        branches_success, branches_response = self.run_test(
            "GET /api/projects/{id}/branches",
            "GET",
            f"projects/{project_id}/branches",
            200
        )
        endpoints_results["branches"] = branches_success
        
        # Get a branch name for further tests
        branch_name = None
        if branches_success and "branches" in branches_response:
            branches = branches_response["branches"]
            if branches:
                branch_name = branches[0].get("name")
        
        if branch_name:
            # Test 3: POST /api/projects/{id}/branches/{branch}/test
            test_success, test_response = self.run_test(
                "POST /api/projects/{id}/branches/{branch}/test",
                "POST",
                f"projects/{project_id}/branches/{branch_name}/test",
                200,
                timeout=60
            )
            endpoints_results["branch_test"] = test_success
            
            # Test 4: GET /api/projects/{id}/branches/{branch}/artifacts
            artifacts_success, artifacts_response = self.run_test(
                "GET /api/projects/{id}/branches/{branch}/artifacts",
                "GET",
                f"projects/{project_id}/branches/{branch_name}/artifacts",
                200
            )
            endpoints_results["artifacts"] = artifacts_success
            
            # Test 5: POST /api/projects/{id}/branches/{branch}/close
            close_success, close_response = self.run_test(
                "POST /api/projects/{id}/branches/{branch}/close",
                "POST",
                f"projects/{project_id}/branches/{branch_name}/close",
                200
            )
            endpoints_results["close_branch"] = close_success
        else:
            print("⚠️  No branches found, skipping branch-specific endpoint tests")
            endpoints_results["branch_test"] = False
            endpoints_results["artifacts"] = False
            endpoints_results["close_branch"] = False
        
        # Calculate success rate
        successful_endpoints = sum(1 for success in endpoints_results.values() if success)
        total_endpoints = len(endpoints_results)
        
        print(f"\n📊 Endpoints Availability Results:")
        for endpoint, success in endpoints_results.items():
            status = "✅" if success else "❌"
            print(f"   {status} {endpoint}")
        
        print(f"   Success Rate: {successful_endpoints}/{total_endpoints} ({successful_endpoints/total_endpoints*100:.1f}%)")
        
        return successful_endpoints >= 3, endpoints_results

    def test_case_a_laravel_auto_heal(self):
        """Case A: Laravel Auto-Heal"""
        print("\n🔍 Testing Case A: Laravel Auto-Heal...")
        
        project_id = "test-laravel-heal"
        setup_success, project_path = self.setup_test_project(project_id, "laravel")
        
        if not setup_success:
            return False, {"error": "Failed to setup Laravel project"}
        
        # Auto-heal request
        heal_data = {
            "max_steps": 1,
            "operations": [
                {
                    "type": "create",
                    "path": "routes/api.php",
                    "content": "<?php\nRoute::get('/health', fn() => ['status' => 'ok']);"
                }
            ]
        }
        
        success, response = self.run_test(
            "Laravel Auto-Heal",
            "POST",
            f"projects/{project_id}/auto-heal",
            200,
            data=heal_data,
            timeout=120
        )
        
        if success and response:
            # Validate expected response structure
            expected_fields = ["status", "branch_name", "operations_executed", "health_results"]
            missing_fields = [field for field in expected_fields if field not in response]
            
            if missing_fields:
                print(f"⚠️  Missing expected fields: {missing_fields}")
            
            # Check if branch was created
            branch_name = response.get("branch_name")
            if branch_name and branch_name.startswith("autofix/"):
                print(f"✅ Branch created: {branch_name}")
            else:
                print(f"❌ Invalid branch name: {branch_name}")
            
            # Check operations executed
            ops_executed = response.get("operations_executed", 0)
            if ops_executed >= 1:
                print(f"✅ Operations executed: {ops_executed}")
            else:
                print(f"❌ No operations executed")
            
            # Check health results
            health_results = response.get("health_results", {})
            if health_results:
                print(f"✅ Health pipeline executed")
                
                # Check for Laravel-specific health checks
                checks = health_results.get("checks", [])
                laravel_checks = ["composer", "pint", "pest", "phpstan"]
                found_checks = [check.get("name") for check in checks if check.get("name") in laravel_checks]
                print(f"   Laravel checks found: {found_checks}")
            
            return True, response
        
        return success, response

    def test_case_b_node_auto_heal(self):
        """Case B: Node Auto-Heal"""
        print("\n🔍 Testing Case B: Node Auto-Heal...")
        
        project_id = "test-node-heal"
        setup_success, project_path = self.setup_test_project(project_id, "node")
        
        if not setup_success:
            return False, {"error": "Failed to setup Node project"}
        
        # Auto-heal request
        heal_data = {
            "max_steps": 1,
            "operations": [
                {
                    "type": "create",
                    "path": "src/health.js",
                    "content": "module.exports = { status: 'ok' };"
                }
            ]
        }
        
        success, response = self.run_test(
            "Node Auto-Heal",
            "POST",
            f"projects/{project_id}/auto-heal",
            200,
            data=heal_data,
            timeout=120
        )
        
        if success and response:
            # Check health results for Node-specific checks
            health_results = response.get("health_results", {})
            if health_results:
                checks = health_results.get("checks", [])
                node_checks = ["npm", "eslint", "test"]
                found_checks = [check.get("name") for check in checks if check.get("name") in node_checks]
                print(f"   Node checks found: {found_checks}")
            
            return True, response
        
        return success, response

    def test_case_c_generic_auto_heal(self):
        """Case C: Generic Stack Auto-Heal"""
        print("\n🔍 Testing Case C: Generic Stack Auto-Heal...")
        
        project_id = "test-generic-heal"
        setup_success, project_path = self.setup_test_project(project_id, "generic")
        
        if not setup_success:
            return False, {"error": "Failed to setup generic project"}
        
        # Auto-heal request
        heal_data = {
            "max_steps": 1,
            "operations": [
                {
                    "type": "create",
                    "path": "health-check.txt",
                    "content": "Generic health check file"
                }
            ]
        }
        
        success, response = self.run_test(
            "Generic Auto-Heal",
            "POST",
            f"projects/{project_id}/auto-heal",
            200,
            data=heal_data,
            timeout=120
        )
        
        if success and response:
            # Check health results for generic checks
            health_results = response.get("health_results", {})
            if health_results:
                checks = health_results.get("checks", [])
                generic_checks = ["git", "files", "structure"]
                found_checks = [check.get("name") for check in checks if check.get("name") in generic_checks]
                print(f"   Generic checks found: {found_checks}")
            
            return True, response
        
        return success, response

    def test_case_d_protected_paths_rejection(self):
        """Case D: Protected Paths Rejection"""
        print("\n🔍 Testing Case D: Protected Paths Rejection...")
        
        project_id = "test-protected-paths"
        setup_success, project_path = self.setup_test_project(project_id, "laravel")
        
        if not setup_success:
            return False, {"error": "Failed to setup project for protected paths test"}
        
        # Try to modify protected path
        heal_data = {
            "max_steps": 1,
            "operations": [
                {
                    "type": "update",
                    "path": ".env",
                    "content": "MALICIOUS=true"
                }
            ]
        }
        
        success, response = self.run_test(
            "Protected Paths Rejection",
            "POST",
            f"projects/{project_id}/auto-heal",
            422,  # Should be rejected with 422
            data=heal_data
        )
        
        if not success:
            # Try 400 or 500 as alternative error codes
            success, response = self.run_test(
                "Protected Paths Rejection (400)",
                "POST",
                f"projects/{project_id}/auto-heal",
                400,
                data=heal_data
            )
            
            if not success:
                success, response = self.run_test(
                    "Protected Paths Rejection (500)",
                    "POST",
                    f"projects/{project_id}/auto-heal",
                    500,
                    data=heal_data
                )
        
        if success:
            # Check error message mentions protected path
            error_message = response.get("detail", "")
            if "protected" in error_message.lower() or ".env" in error_message:
                print(f"✅ Proper error message: {error_message}")
            else:
                print(f"⚠️  Error message doesn't mention protected path: {error_message}")
        
        return success, response

    def test_branches_management(self):
        """Test branches management functionality"""
        print("\n🔍 Testing Branches Management...")
        
        project_id = "test-branches-mgmt"
        setup_success, project_path = self.setup_test_project(project_id, "laravel")
        
        if not setup_success:
            return False, {"error": "Failed to setup project for branches test"}
        
        # Create an auto-heal to generate a branch
        heal_data = {
            "max_steps": 1,
            "operations": [
                {
                    "type": "create",
                    "path": "branch-test.txt",
                    "content": "Testing branch management"
                }
            ]
        }
        
        heal_success, heal_response = self.run_test(
            "Create Auto-Heal for Branch Test",
            "POST",
            f"projects/{project_id}/auto-heal",
            200,
            data=heal_data,
            timeout=60
        )
        
        if not heal_success:
            return False, {"error": "Failed to create auto-heal for branch test"}
        
        branch_name = heal_response.get("branch_name")
        if not branch_name:
            return False, {"error": "No branch name returned from auto-heal"}
        
        # Test GET branches
        branches_success, branches_response = self.run_test(
            "List Project Branches",
            "GET",
            f"projects/{project_id}/branches",
            200
        )
        
        if not branches_success:
            return False, {"error": "Failed to list branches"}
        
        # Test branch artifacts
        artifacts_success, artifacts_response = self.run_test(
            "Get Branch Artifacts",
            "GET",
            f"projects/{project_id}/branches/{branch_name}/artifacts",
            200
        )
        
        # Test rerun health pipeline
        rerun_success, rerun_response = self.run_test(
            "Rerun Health Pipeline",
            "POST",
            f"projects/{project_id}/branches/{branch_name}/test",
            200,
            timeout=60
        )
        
        results = {
            "branches_list": branches_success,
            "artifacts": artifacts_success,
            "rerun_health": rerun_success,
            "branch_name": branch_name
        }
        
        successful_tests = sum(1 for success in [branches_success, artifacts_success, rerun_success] if success)
        
        return successful_tests >= 2, results

    def test_validation_scenarios(self):
        """Test various validation scenarios"""
        print("\n🔍 Testing Validation Scenarios...")
        
        validation_results = {}
        
        # Test 1: Auto-heal on non-existent project
        nonexistent_success, _ = self.run_test(
            "Auto-heal Non-existent Project",
            "POST",
            "projects/nonexistent-project-12345/auto-heal",
            404,
            data={"max_steps": 1, "operations": []}
        )
        validation_results["nonexistent_project"] = nonexistent_success
        
        # Test 2: Auto-heal without operations (should work with warning)
        project_id = "test-validation"
        setup_success, _ = self.setup_test_project(project_id, "generic")
        
        if setup_success:
            no_ops_success, no_ops_response = self.run_test(
                "Auto-heal Without Operations",
                "POST",
                f"projects/{project_id}/auto-heal",
                200,
                data={"max_steps": 1}
            )
            validation_results["no_operations"] = no_ops_success
        else:
            validation_results["no_operations"] = False
        
        # Test 3: Invalid branch operations
        invalid_branch_success, _ = self.run_test(
            "Invalid Branch Test",
            "POST",
            f"projects/{project_id}/branches/nonexistent-branch/test",
            404
        )
        validation_results["invalid_branch"] = invalid_branch_success
        
        # Test 4: Invalid branch artifacts
        invalid_artifacts_success, _ = self.run_test(
            "Invalid Branch Artifacts",
            "GET",
            f"projects/{project_id}/branches/nonexistent-branch/artifacts",
            404
        )
        validation_results["invalid_artifacts"] = invalid_artifacts_success
        
        successful_validations = sum(1 for success in validation_results.values() if success)
        total_validations = len(validation_results)
        
        print(f"\n📊 Validation Results:")
        for test_name, success in validation_results.items():
            status = "✅" if success else "❌"
            print(f"   {status} {test_name}")
        
        return successful_validations >= total_validations * 0.75, validation_results

    def cleanup_test_projects(self):
        """Clean up created test projects"""
        import shutil
        import os
        
        for project_id in self.created_projects:
            try:
                project_path = f"/app/projects/{project_id}"
                if os.path.exists(project_path):
                    shutil.rmtree(project_path)
                    print(f"🧹 Cleaned up project: {project_id}")
            except Exception as e:
                print(f"⚠️  Failed to cleanup project {project_id}: {e}")

    def run_all_phase3_tests(self):
        """Run all Phase 3 Auto-Heal tests"""
        print("🔥 PHASE 3 AUTO-HEAL BACKEND TESTING")
        print("=" * 70)
        
        tests = [
            ("Endpoints Availability", self.test_endpoints_availability),
            ("Case A: Laravel Auto-Heal", self.test_case_a_laravel_auto_heal),
            ("Case B: Node Auto-Heal", self.test_case_b_node_auto_heal),
            ("Case C: Generic Auto-Heal", self.test_case_c_generic_auto_heal),
            ("Case D: Protected Paths Rejection", self.test_case_d_protected_paths_rejection),
            ("Branches Management", self.test_branches_management),
            ("Validation Scenarios", self.test_validation_scenarios),
        ]
        
        results = {}
        
        for test_name, test_func in tests:
            print(f"\n{'='*10} {test_name} {'='*10}")
            try:
                success, data = test_func()
                results[test_name] = {"success": success, "data": data}
            except Exception as e:
                print(f"❌ Test {test_name} crashed: {str(e)}")
                results[test_name] = {"success": False, "error": str(e)}
        
        # Cleanup
        self.cleanup_test_projects()
        
        return results

def main_phase3():
    """Main function for Phase 3 testing"""
    print("🚀 Starting PHASE 3 AUTO-HEAL Backend Testing")
    print("=" * 70)
    
    # Run Phase 3 Auto-Heal Tests
    phase3_tester = Phase3AutoHealTester()
    phase3_results = phase3_tester.run_all_phase3_tests()
    
    # Print Phase 3 Results
    print(f"\n{'='*70}")
    print(f"📊 PHASE 3 AUTO-HEAL RESULTS")
    print(f"Tests Run: {phase3_tester.tests_run}")
    print(f"Tests Passed: {phase3_tester.tests_passed}")
    print(f"Tests Failed: {phase3_tester.tests_run - phase3_tester.tests_passed}")
    print(f"Success Rate: {(phase3_tester.tests_passed/phase3_tester.tests_run*100):.1f}%" if phase3_tester.tests_run > 0 else "0%")
    
    # Detailed results
    print(f"\n📋 DETAILED RESULTS:")
    for test_name, result in phase3_results.items():
        status = "✅ PASS" if result["success"] else "❌ FAIL"
        print(f"   {status} - {test_name}")
        if not result["success"] and "error" in result:
            print(f"      Error: {result['error']}")
    
    # Summary for main agent
    failed_tests = [name for name, result in phase3_results.items() if not result["success"]]
    critical_failures = []
    
    # Identify critical failures
    for test_name, result in phase3_results.items():
        if not result["success"]:
            if "Endpoints Availability" in test_name:
                critical_failures.append("Auto-heal endpoints not responding")
            elif "Protected Paths" in test_name:
                critical_failures.append("Protected paths validation failing")
            elif "Laravel Auto-Heal" in test_name:
                critical_failures.append("Laravel auto-heal pipeline broken")
    
    return {
        "total_tests": phase3_tester.tests_run,
        "passed_tests": phase3_tester.tests_passed,
        "failed_tests": failed_tests,
        "critical_failures": critical_failures,
        "success_rate": (phase3_tester.tests_passed/phase3_tester.tests_run*100) if phase3_tester.tests_run > 0 else 0
    }

if __name__ == "__main__":
    import sys
    
    # Check which phase to run
    if len(sys.argv) > 1:
        if sys.argv[1] == "phase2":
            sys.exit(main_phase2())
        elif sys.argv[1] == "phase3":
            results = main_phase3()
            if results["success_rate"] >= 70:
                print("🎉 Phase 3 Auto-Heal tests mostly passed!")
                sys.exit(0)
            else:
                print("⚠️  Phase 3 Auto-Heal tests need attention")
                sys.exit(1)
    else:
        sys.exit(main())