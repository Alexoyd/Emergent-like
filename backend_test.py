import requests
import sys
import json
import time
from datetime import datetime

class AIAgentOrchestratorTester:
    def __init__(self, base_url="https://codeforge-agent.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.tests_run = 0
        self.tests_passed = 0
        self.created_run_id = None

    def run_test(self, name, method, endpoint, expected_status, data=None, timeout=10):
        """Run a single API test"""
        url = f"{self.api_url}/{endpoint}" if endpoint else f"{self.api_url}/"
        headers = {'Content-Type': 'application/json'}

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        print(f"   URL: {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=timeout)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=timeout)

            print(f"   Status Code: {response.status_code}")
            
            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Expected {expected_status}, got {response.status_code}")
                
                # Try to parse JSON response
                try:
                    response_data = response.json()
                    print(f"   Response: {json.dumps(response_data, indent=2)[:200]}...")
                    return True, response_data
                except:
                    print(f"   Response: {response.text[:200]}...")
                    return True, {}
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                print(f"   Response: {response.text[:200]}...")
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

    def test_create_run(self):
        """Test creating a new run"""
        run_data = {
            "goal": "Create a simple Laravel API endpoint for user registration",
            "project_path": "/tmp/test-project",
            "stack": "laravel",
            "max_steps": 5,
            "max_retries_per_step": 1,
            "daily_budget_eur": 2.0
        }
        
        success, response = self.run_test(
            "Create New Run",
            "POST",
            "runs",
            200,  # Expecting 200, but might be 201
            data=run_data,
            timeout=15
        )
        
        if not success:
            # Try with 201 status code
            success, response = self.run_test(
                "Create New Run (201)",
                "POST", 
                "runs",
                201,
                data=run_data,
                timeout=15
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
                "file_path": "/etc/hostname"  # This should exist on most systems
            }
        ]
        
        read_success, _ = self.run_test(
            "File Read Operation",
            "POST",
            "files/read",
            200,
            data=read_data
        )
        
        # Test file write (to a safe location)
        write_data = [
            {
                "operation": "write",
                "file_path": "/tmp/test_file.txt",
                "content": "This is a test file created by the API test"
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
            422,  # Expecting validation error
            data=invalid_run_data
        )
        
        if not success:
            # Try 400 status code
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
            "runs/nonexistent-id",
            404
        )
        
        return success and nonexistent_success, {}

    def test_database_integration(self):
        """Test if runs are being stored in database correctly"""
        # Create a run and then verify it appears in the list
        run_data = {
            "goal": "Test database integration",
            "stack": "laravel",
            "max_steps": 3,
            "daily_budget_eur": 1.0
        }
        
        create_success, create_response = self.run_test(
            "Database Integration - Create",
            "POST",
            "runs",
            200,
            data=run_data
        )
        
        if not create_success:
            create_success, create_response = self.run_test(
                "Database Integration - Create (201)",
                "POST",
                "runs",
                201,
                data=run_data
            )
        
        if create_success and 'id' in create_response:
            test_run_id = create_response['id']
            
            # Wait a moment for database write
            time.sleep(1)
            
            # Verify it appears in the list
            list_success, list_response = self.run_test(
                "Database Integration - List",
                "GET",
                "runs",
                200
            )
            
            if list_success and isinstance(list_response, list):
                # Check if our run is in the list
                found_run = any(run.get('id') == test_run_id for run in list_response)
                if found_run:
                    print("✅ Database Integration - Run found in list")
                    return True, {}
                else:
                    print("❌ Database Integration - Run not found in list")
                    return False, {}
        
        return False, {}

def main():
    print("🚀 Starting AI Agent Orchestrator API Tests")
    print("=" * 60)
    
    tester = AIAgentOrchestratorTester()
    
    # Run all tests
    tests = [
        ("API Health Check", tester.test_health_check),
        ("Create Run", tester.test_create_run),
        ("Get Run", tester.test_get_run),
        ("List Runs", tester.test_list_runs),
        ("File Operations", tester.test_file_operations),
        ("Database Integration", tester.test_database_integration),
        ("Invalid Requests", tester.test_invalid_requests),
        ("Cancel Run", tester.test_cancel_run),
    ]
    
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        try:
            test_func()
        except Exception as e:
            print(f"❌ Test {test_name} crashed: {str(e)}")
    
    # Print final results
    print(f"\n{'='*60}")
    print(f"📊 FINAL RESULTS")
    print(f"Tests Run: {tester.tests_run}")
    print(f"Tests Passed: {tester.tests_passed}")
    print(f"Tests Failed: {tester.tests_run - tester.tests_passed}")
    print(f"Success Rate: {(tester.tests_passed/tester.tests_run*100):.1f}%" if tester.tests_run > 0 else "0%")
    
    if tester.tests_passed == tester.tests_run:
        print("🎉 All tests passed!")
        return 0
    else:
        print("⚠️  Some tests failed - check logs above")
        return 1

if __name__ == "__main__":
    sys.exit(main())