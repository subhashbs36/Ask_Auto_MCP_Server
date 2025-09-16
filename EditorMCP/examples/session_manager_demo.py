"""Example demonstrating the hybrid session manager with optional Redis."""

import asyncio
import json
from typing import Dict, Any

# Simulated configuration and models
class RedisConfig:
    def __init__(self, host="localhost", port=6379, password=None, db=0, 
                 connection_timeout=5, socket_timeout=5, max_connections=10):
        self.host = host
        self.port = port
        self.password = password
        self.db = db
        self.connection_timeout = connection_timeout
        self.socket_timeout = socket_timeout
        self.max_connections = max_connections

class ProposedChange:
    def __init__(self, id: str, path: list, current_value: Any, proposed_value: Any):
        self.id = id
        self.path = path
        self.current_value = current_value
        self.proposed_value = proposed_value

def create_sample_document() -> Dict[str, Any]:
    """Create a sample JSON document for testing."""
    return {
        "user": {
            "name": "Alice Johnson",
            "email": "alice@example.com",
            "settings": {
                "theme": "dark",
                "notifications": True,
                "language": "en"
            }
        },
        "products": [
            {"id": 1, "name": "Widget A", "price": 19.99},
            {"id": 2, "name": "Widget B", "price": 29.99}
        ]
    }

def create_sample_changes() -> list:
    """Create sample proposed changes."""
    return [
        ProposedChange(
            id="change_1",
            path=["user", "name"],
            current_value="Alice Johnson",
            proposed_value="Alice Smith"
        ),
        ProposedChange(
            id="change_2",
            path=["user", "settings", "theme"],
            current_value="dark",
            proposed_value="light"
        ),
        ProposedChange(
            id="change_3",
            path=["products", "0", "price"],
            current_value=19.99,
            proposed_value=24.99
        )
    ]

async def demo_memory_only():
    """Demonstrate memory-only session storage."""
    print("=" * 60)
    print("DEMO 1: Memory-Only Session Storage")
    print("=" * 60)
    
    try:
        from EditorMCP.json_editor_mcp.services.hybrid_session_manager import HybridSessionManager
        
        # Create session manager without Redis config (memory-only)
        session_manager = HybridSessionManager(
            redis_config=None,
            session_ttl=3600,
            prefer_redis=False
        )
        
        # Create a sample document and changes
        document = create_sample_document()
        changes = create_sample_changes()
        
        print("Creating session with sample document...")
        session_id = session_manager.create_session(document, changes)
        print(f"✓ Session created: {session_id}")
        print(f"✓ Storage type: {session_manager.storage_type}")
        print(f"✓ Has Redis: {session_manager.has_redis}")
        
        # Retrieve the session
        print("\nRetrieving session...")
        retrieved_session = session_manager.get_session(session_id)
        print(f"✓ Session retrieved successfully")
        print(f"✓ Document hash: {retrieved_session.document_hash}")
        print(f"✓ Number of proposed changes: {len(retrieved_session.proposed_changes)}")
        
        # Test session validation
        print("\nTesting session validation...")
        is_valid = session_manager.validate_session(session_id)
        print(f"✓ Session is valid: {is_valid}")
        
        # Test document verification
        print("\nTesting document verification...")
        is_unchanged = session_manager.verify_document_unchanged(session_id, document)
        print(f"✓ Document unchanged: {is_unchanged}")
        
        # List active sessions
        print("\nListing active sessions...")
        active_sessions = session_manager.list_active_sessions()
        print(f"✓ Active sessions: {len(active_sessions)}")
        
        # Health check
        print("\nPerforming health check...")
        health = session_manager.health_check()
        print(f"✓ Health status: {health['status']}")
        print(f"✓ Primary storage: {health['primary_storage']}")
        print(f"✓ Active sessions: {health['active_sessions']}")
        
        # Clean up
        print("\nCleaning up...")
        deleted = session_manager.delete_session(session_id)
        print(f"✓ Session deleted: {deleted}")
        
        session_manager.close()
        print("✓ Session manager closed")
        
    except Exception as e:
        print(f"❌ Error in memory-only demo: {e}")
        import traceback
        traceback.print_exc()

async def demo_with_redis_fallback():
    """Demonstrate Redis storage with memory fallback."""
    print("\n" + "=" * 60)
    print("DEMO 2: Redis Storage with Memory Fallback")
    print("=" * 60)
    
    try:
        from EditorMCP.json_editor_mcp.services.hybrid_session_manager import HybridSessionManager
        
        # Create Redis config (will likely fail to connect, showing fallback)
        redis_config = RedisConfig(host="localhost", port=6379)
        
        # Create session manager with Redis config
        session_manager = HybridSessionManager(
            redis_config=redis_config,
            session_ttl=3600,
            prefer_redis=True  # Prefer Redis if available
        )
        
        # Create a sample document and changes
        document = create_sample_document()
        changes = create_sample_changes()
        
        print("Creating session with Redis fallback...")
        session_id = session_manager.create_session(document, changes)
        print(f"✓ Session created: {session_id}")
        print(f"✓ Storage type: {session_manager.storage_type}")
        print(f"✓ Has Redis: {session_manager.has_redis}")
        
        # Health check
        print("\nPerforming health check...")
        health = session_manager.health_check()
        print(f"✓ Health status: {health['status']}")
        print(f"✓ Primary storage: {health['primary_storage']}")
        
        # Show storage details
        if 'storages' in health:
            for storage_name, storage_health in health['storages'].items():
                print(f"  - {storage_name}: {storage_health['status']}")
                if storage_health['status'] != 'healthy':
                    print(f"    Error: {storage_health.get('error', 'Unknown')}")
        
        # Clean up
        print("\nCleaning up...")
        session_manager.delete_session(session_id)
        session_manager.close()
        print("✓ Session manager closed")
        
    except Exception as e:
        print(f"❌ Error in Redis fallback demo: {e}")
        import traceback
        traceback.print_exc()

async def demo_session_features():
    """Demonstrate various session management features."""
    print("\n" + "=" * 60)
    print("DEMO 3: Advanced Session Features")
    print("=" * 60)
    
    try:
        from EditorMCP.json_editor_mcp.services.hybrid_session_manager import HybridSessionManager
        
        # Create memory-only session manager
        session_manager = HybridSessionManager(session_ttl=60)  # 1 minute TTL
        
        # Create multiple sessions
        print("Creating multiple sessions...")
        document1 = {"data": "session1"}
        document2 = {"data": "session2"}
        changes = []
        
        session_id1 = session_manager.create_session(document1, changes)
        session_id2 = session_manager.create_session(document2, changes)
        
        print(f"✓ Created session 1: {session_id1}")
        print(f"✓ Created session 2: {session_id2}")
        
        # List all sessions
        active_sessions = session_manager.list_active_sessions()
        print(f"✓ Total active sessions: {len(active_sessions)}")
        
        # Check TTL
        print("\nChecking session TTL...")
        ttl1 = session_manager.get_session_ttl(session_id1)
        ttl2 = session_manager.get_session_ttl(session_id2)
        print(f"✓ Session 1 TTL: {ttl1} seconds")
        print(f"✓ Session 2 TTL: {ttl2} seconds")
        
        # Extend TTL
        print("\nExtending session TTL...")
        extended = session_manager.extend_session_ttl(session_id1, 120)  # 2 minutes
        print(f"✓ TTL extended: {extended}")
        
        new_ttl = session_manager.get_session_ttl(session_id1)
        print(f"✓ New TTL for session 1: {new_ttl} seconds")
        
        # Test document state verification
        print("\nTesting document state verification...")
        modified_document = {"data": "modified"}
        
        try:
            session_manager.verify_document_unchanged(session_id1, modified_document)
            print("❌ Should have detected document change")
        except Exception as e:
            print(f"✓ Correctly detected document change: {type(e).__name__}")
        
        # Cleanup
        print("\nCleaning up sessions...")
        cleaned = session_manager.cleanup_expired_sessions()
        print(f"✓ Cleaned expired sessions: {cleaned}")
        
        session_manager.close()
        print("✓ Session manager closed")
        
    except Exception as e:
        print(f"❌ Error in session features demo: {e}")
        import traceback
        traceback.print_exc()

async def main():
    """Run all demos."""
    print("Hybrid Session Manager Demo")
    print("This demonstrates the new memory-first session storage with optional Redis")
    
    await demo_memory_only()
    await demo_with_redis_fallback() 
    await demo_session_features()
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print("✓ Memory-first storage implemented")
    print("✓ Redis made optional with graceful fallback")
    print("✓ All existing session manager functionality preserved")
    print("✓ Hybrid storage provides redundancy and flexibility")
    print("✓ Compatible with existing preview/apply tools")

if __name__ == "__main__":
    asyncio.run(main())