#!/usr/bin/env python3
"""
Test script for the JSON Editor REST API Server
"""

import json
import requests
import time
from typing import Dict, Any

# Server configuration
BASE_URL = "http://localhost:8000"

def create_text_node(value: str, node_type: str = "text") -> Dict[str, str]:
    """Helper function to create a properly formatted text node."""
    return {"type": node_type, "value": str(value)}

def create_test_document() -> Dict[str, Any]:
    """Create a test document with the proper format."""
    with open(r"dump\correspondence-automation-dev-db.letter_type_block.json", "r") as f:
        data_array = json.load(f)
    # Get a specific JSON object by index (e.g., index 0)
    data = data_array[1] if data_array else {}
    
    # IMPORTANT: Parse the JSON string content into objects
    # This fixes the issue where MongoDB stores content as JSON strings
    if isinstance(data.get("content"), str):
        try:
            data["content"] = json.loads(data["content"])
            print("✅ Parsed JSON string content into objects")
        except json.JSONDecodeError as e:
            print(f"❌ Failed to parse content: {e}")
    
    print(f"Document content type after parsing: {type(data.get('content'))}")
    return data

def test_server_health():
    """Test server health endpoint."""
    print("Testing server health...")
    try:
        response = requests.get(f"{BASE_URL}/health")
        print(f"Health check status: {response.status_code}")
        if response.status_code == 200:
            health_data = response.json()
            print(f"Server status: {health_data.get('status')}")
            print(f"Components: {health_data.get('components', {})}")
        else:
            print(f"Health check failed: {response.text}")
        return response.status_code == 200
    except Exception as e:
        print(f"Health check error: {e}")
        return False

def test_server_info():
    """Test server info endpoint."""
    print("\nTesting server info...")
    try:
        response = requests.get(f"{BASE_URL}/info")
        print(f"Info status: {response.status_code}")
        if response.status_code == 200:
            info_data = response.json()
            print(f"Server name: {info_data.get('name')}")
            print(f"Version: {info_data.get('version')}")
            print(f"LLM Provider: {info_data.get('config', {}).get('llm_provider')}")
        else:
            print(f"Info request failed: {response.text}")
        return response.status_code == 200
    except Exception as e:
        print(f"Info request error: {e}")
        return False

def test_preview_and_apply():
    """Test the preview and apply workflow."""
    print("\nTesting preview and apply workflow...")
    
    # Create a test document with the proper format
    test_document = create_test_document()
    
    print("Original document structure:")
    # user_data = test_document.get("user", {})
    # print(f"  Name: {user_data.get('name', {}).get('value', 'N/A')}")
    # print(f"  Age: {user_data.get('age', {}).get('value', 'N/A')}")
    # print(f"  Email: {user_data.get('email', {}).get('value', 'N/A')}")
    
    # Test preview
    print("\n1. Testing preview...")
    preview_request = {
        "document": test_document,
        "instruction": "Change the PO Box number to '99999' and update the city to 'Los Angeles'"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/preview", json=preview_request)
        print(f"Preview status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"Preview failed: {response.text}")
            return False
        
        preview_data = response.json()
        session_id = preview_data.get("session_id")
        changes = preview_data.get("changes", [])
        
        print(f"Session ID: {session_id}")
        print(f"Number of changes: {len(changes)}")
        
        if changes:
            print("Proposed changes:")
            for i, change in enumerate(changes[:3]):  # Show first 3 changes
                description = change.get('description', 'No description')
                path = " -> ".join(change.get('path', []))
                current_val = change.get('current_value', 'N/A')
                proposed_val = change.get('proposed_value', 'N/A')
                print(f"  {i+1}. {description}")
                print(f"     Path: {path}")
                print(f"     Change: '{current_val}' -> '{proposed_val}'")
        
        if not session_id:
            print("No session ID returned from preview")
            return False
        
        # Test apply
        print("\n2. Testing apply...")
        apply_request = {
            "session_id": session_id
        }
        
        response = requests.post(f"{BASE_URL}/apply", json=apply_request)
        print(f"Apply status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"Apply failed: {response.text}")
            return False
        
        apply_data = response.json()
        modified_document = apply_data.get("modified_document")
        applied_changes = apply_data.get("applied_changes", [])
        
        print(f"Number of applied changes: {len(applied_changes)}")
        
        if applied_changes:
            print("Applied changes:")
            for i, change in enumerate(applied_changes[:3]):
                path = " -> ".join(change.get('path', []))
                old_val = change.get('old_value', 'N/A')
                new_val = change.get('new_value', 'N/A')
                print(f"  {i+1}. Path: {path}")
                print(f"     Changed: '{old_val}' -> '{new_val}'")
        
        # if modified_document:
        #     print("Modified document (user section):")
        #     user_data = modified_document.get("user", {})
        #     name_node = user_data.get("name", {})
        #     age_node = user_data.get("age", {})
        #     print(f"  Name: {name_node.get('value', 'N/A')}")
        #     print(f"  Age: {age_node.get('value', 'N/A')}")
        
        # Test partial application (apply only first change)
        if len(changes) > 1:
            print("\n3. Testing partial apply (first change only)...")
            first_change_id = changes[0].get('id')
            if first_change_id:
                partial_apply_request = {
                    "session_id": session_id,
                    "confirmed_changes": [first_change_id]
                }
                
                # Note: This will fail because session was already consumed, but shows the API
                print(f"Would apply only change: {first_change_id}")
        
        return True
        
    except Exception as e:
        print(f"Preview/Apply test error: {e}")
        return False

def test_partial_apply():
    """Test applying only specific changes."""
    print("\nTesting partial apply workflow...")
    
    # Create a test document
    test_document = create_test_document()
    
    try:
        # Preview with multiple changes
        preview_request = {
            "document": test_document,
            "instruction": "Change the PO Box to '55555', update the city to 'San Francisco', and change the zip code to '94102'"
        }
        
        response = requests.post(f"{BASE_URL}/preview", json=preview_request)
        if response.status_code != 200:
            print(f"Preview failed: {response.text}")
            return False
        
        preview_data = response.json()
        session_id = preview_data.get("session_id")
        changes = preview_data.get("changes", [])
        
        print(f"Found {len(changes)} changes")
        
        if len(changes) >= 2:
            # Apply only the first change
            first_change_id = changes[0].get('id')
            print(f"Applying only first change: {first_change_id}")
            
            apply_request = {
                "session_id": session_id,
                "confirmed_changes": [first_change_id]
            }
            
            response = requests.post(f"{BASE_URL}/apply", json=apply_request)
            if response.status_code == 200:
                apply_data = response.json()
                applied_changes = apply_data.get("applied_changes", [])
                print(f"Successfully applied {len(applied_changes)} change(s)")
                return True
            else:
                print(f"Partial apply failed: {response.text}")
                return False
        else:
            print("Not enough changes to test partial apply")
            return True
            
    except Exception as e:
        print(f"Partial apply test error: {e}")
        return False

def test_sessions_endpoint():
    """Test the sessions listing endpoint."""
    print("\nTesting sessions endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/sessions")
        print(f"Sessions status: {response.status_code}")
        
        if response.status_code == 200:
            sessions_data = response.json()
            active_count = sessions_data.get("active_sessions", 0)
            print(f"Active sessions: {active_count}")
            
            # Show session details if any exist
            sessions = sessions_data.get("sessions", {})
            if sessions:
                print("Session details:")
                for session_id, details in list(sessions.items())[:2]:  # Show first 2
                    age = details.get("age_seconds", 0)
                    instruction = details.get("instruction", "N/A")[:50] + "..." if len(details.get("instruction", "")) > 50 else details.get("instruction", "N/A")
                    print(f"  {session_id[:16]}...: {age:.1f}s old, instruction: {instruction}")
        else:
            print(f"Sessions request failed: {response.text}")
        
        return response.status_code == 200
    except Exception as e:
        print(f"Sessions test error: {e}")
        return False

def main():
    """Run all tests."""
    print("JSON Editor REST API Test Suite")
    print("=" * 40)
    
    # Test basic connectivity
    print("Testing server connectivity...")
    try:
        response = requests.get(f"{BASE_URL}/")
        if response.status_code == 200:
            print("✓ Server is running")
        else:
            print(f"✗ Server returned status {response.status_code}")
            return
    except Exception as e:
        print(f"✗ Cannot connect to server: {e}")
        print("Make sure the server is running on http://localhost:8000")
        print("Start the server with: python start_server.py")
        return
    
    # Run tests
    tests = [
        ("Health Check", test_server_health),
        ("Server Info", test_server_info),
        ("Sessions Endpoint", test_sessions_endpoint),
        ("Preview and Apply", test_preview_and_apply),
        ("Partial Apply", test_partial_apply),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n{'='*20}")
        try:
            result = test_func()
            results.append((test_name, result))
            print(f"✓ {test_name}: {'PASSED' if result else 'FAILED'}")
        except Exception as e:
            results.append((test_name, False))
            print(f"✗ {test_name}: ERROR - {e}")
    
    # Summary
    print(f"\n{'='*40}")
    print("TEST SUMMARY")
    print(f"{'='*40}")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "PASSED" if result else "FAILED"
        print(f"{test_name}: {status}")
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Your JSON Editor REST API is working correctly.")
    else:
        print("⚠️  Some tests failed. Check the error messages above.")

if __name__ == "__main__":
    main()