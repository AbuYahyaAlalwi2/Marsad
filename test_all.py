import sys
sys.path.insert(0, '.')

def test_library():
    print("="*60)
    print("TESTING LIBRARY")
    print("="*60)
    
    # Test 1: Imports
    try:
        from marsad import AgentSwarm, Workflow, SmartRequest, KeyVault
        print("✓ Test 1: Imports successful")
    except Exception as e:
        print(f"✗ Test 1 failed: {e}")
        return False
    
    # Test 2: AgentSwarm
    try:
        swarm = AgentSwarm(count=100)
        result = swarm.deploy()
        assert result["status"] == "success"
        print("✓ Test 2: AgentSwarm working")
    except Exception as e:
        print(f"✗ Test 2 failed: {e}")
        return False
    
    # Test 3: Workflow
    try:
        wf = Workflow(num_workers=2)
        result = wf.run_full_workflow()
        assert result["status"] == "complete"
        print("✓ Test 3: Workflow working")
    except Exception as e:
        print(f"✗ Test 3 failed: {e}")
        return False
    
    # Test 4: IP Rotation
    try:
        smart = SmartRequest()
        stats = smart.rotator.get_stats()
        print(f"✓ Test 4: IP Rotation working ({stats['total_proxies']} proxies)")
    except Exception as e:
        print(f"✗ Test 4 failed: {e}")
        return False
    
    # Test 5: KeyVault
    try:
        vault = KeyVault()
        vault.save_key("test_platform", "test_key_12345")
        key = vault.get_key("test_platform")
        assert key == "test_key_12345"
        print("✓ Test 5: KeyVault working")
    except Exception as e:
        print(f"✗ Test 5 failed: {e}")
        return False
    
    return True

def test_api_server():
    print("\n" + "="*60)
    print("TESTING API SERVER")
    print("="*60)
    
    try:
        import subprocess
        import time
        import requests
        
        # Start server
        proc = subprocess.Popen(
            [sys.executable, "api_server.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        time.sleep(3)
        
        # Test endpoints
        resp = requests.get("http://localhost:5000/api/status", timeout=5)
        assert resp.status_code == 200
        print("✓ API /api/status working")
        
        resp = requests.get("http://localhost:5000/api/logs", timeout=5)
        assert resp.status_code == 200
        print("✓ API /api/logs working")
        
        # Stop server
        proc.terminate()
        return True
        
    except Exception as e:
        print(f"✗ API test failed: {e}")
        return False

if __name__ == "__main__":
    lib_ok = test_library()
    api_ok = test_api_server()
    
    print("\n" + "="*60)
    print("RESULTS:")
    print(f"  Library: {'✓ PASS' if lib_ok else '✗ FAIL'}")
    print(f"  API Server: {'✓ PASS' if api_ok else '✗ FAIL'}")
    print("="*60)
