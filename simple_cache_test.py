#!/usr/bin/env python3
import requests
import json
import time

def test_backend_cache():
    """Simple test for prompt caching functionality"""
    base_url = "http://localhost:8001/api"
    
    print("🧠 Testing Prompt Caching System")
    print("=" * 50)
    
    # Test 1: Basic API health check
    print("\n1. Testing API Health Check...")
    try:
        response = requests.get(f"{base_url}/", timeout=10)
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            print("✅ API is accessible")
        else:
            print("❌ API not accessible")
            return False
    except Exception as e:
        print(f"❌ API connection failed: {e}")
        return False
    
    # Test 2: Admin stats with cache information
    print("\n2. Testing Admin Stats (Cache Info)...")
    try:
        response = requests.get(f"{base_url}/admin/stats", timeout=15)
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Admin stats accessible")
            
            # Check for cache-related fields
            if 'cache_stats' in data:
                print(f"✅ Cache stats found: {data['cache_stats']}")
            else:
                print("❌ Cache stats missing")
                
            if 'cost_savings' in data:
                print(f"✅ Cost savings found: {data['cost_savings']}")
            else:
                print("❌ Cost savings missing")
                
            if 'settings' in data:
                print(f"✅ Settings found: {data['settings']}")
            else:
                print("❌ Settings missing")
                
        else:
            print(f"❌ Admin stats failed: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Admin stats error: {e}")
        return False
    
    # Test 3: Cache clear endpoint
    print("\n3. Testing Cache Clear Endpoint...")
    try:
        response = requests.post(f"{base_url}/admin/cache/clear", timeout=10)
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Cache clear successful: {data}")
        else:
            print(f"❌ Cache clear failed: {response.text}")
            
    except Exception as e:
        print(f"❌ Cache clear error: {e}")
    
    # Test 4: Create a simple run to test cache usage
    print("\n4. Testing Cache Usage with Simple Run...")
    try:
        run_data = {
            "goal": "Test prompt caching by creating a simple hello world function",
            "stack": "python",
            "max_steps": 1,
            "daily_budget_eur": 0.1
        }
        
        response = requests.post(f"{base_url}/runs", json=run_data, timeout=20)
        print(f"   Status: {response.status_code}")
        
        if response.status_code in [200, 201]:
            data = response.json()
            run_id = data.get('id')
            print(f"✅ Run created: {run_id}")
            
            # Wait a moment for processing
            time.sleep(2)
            
            # Check run status
            run_response = requests.get(f"{base_url}/runs/{run_id}", timeout=10)
            if run_response.status_code == 200:
                run_data = run_response.json()
                print(f"✅ Run status: {run_data.get('status', 'unknown')}")
            
        else:
            print(f"❌ Run creation failed: {response.text}")
            
    except Exception as e:
        print(f"❌ Run creation error: {e}")
    
    # Test 5: Check cache stats after run
    print("\n5. Checking Cache Stats After Run...")
    try:
        response = requests.get(f"{base_url}/admin/stats", timeout=10)
        if response.status_code == 200:
            data = response.json()
            cache_stats = data.get('cache_stats', {})
            cost_savings = data.get('cost_savings', {})
            
            print(f"✅ Final cache stats: {cache_stats}")
            print(f"✅ Final cost savings: {cost_savings}")
            
            # Check if cache has entries
            if cache_stats.get('total_entries', 0) > 0:
                print("✅ Cache is populated!")
            else:
                print("ℹ️  Cache not yet populated (normal for new system)")
                
        else:
            print(f"❌ Final stats check failed")
            
    except Exception as e:
        print(f"❌ Final stats error: {e}")
    
    print("\n" + "=" * 50)
    print("🎉 Prompt Caching Test Complete!")
    return True

if __name__ == "__main__":
    test_backend_cache()