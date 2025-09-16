"""Hybrid session manager with memory-first and optional Redis storage."""

import hashlib
import json
import secrets
import uuid
import logging
from datetime import datetime, UTC
from typing import Any, Dict, List, Optional

from ..config.models import RedisConfig
from ..models.core import ProposedChange
from ..models.session import PreviewSession
from ..models.errors import SessionException
from .session_storage import InMemorySessionStorage, RedisSessionStorage


class HybridSessionManager:
    """Manages preview sessions with memory-first storage and optional Redis fallback."""
    
    def __init__(self, redis_config: Optional[RedisConfig] = None, session_ttl: int = 3600, prefer_redis: bool = False):
        """
        Initialize the hybrid session manager.
        
        Args:
            redis_config: Optional Redis configuration for persistent storage
            session_ttl: Session time-to-live in seconds (default: 1 hour)
            prefer_redis: If True and Redis is available, prefer Redis over memory storage
        """
        self.session_ttl = session_ttl
        self.prefer_redis = prefer_redis
        self.logger = logging.getLogger(__name__)
        
        # Initialize storage backends
        self.memory_storage = InMemorySessionStorage()
        self.redis_storage: Optional[RedisSessionStorage] = None
        
        # Try to initialize Redis storage if config is provided
        if redis_config:
            try:
                self.redis_storage = RedisSessionStorage(redis_config)
                # Test Redis connection
                self.redis_storage.health_check()
                self.logger.info("Redis storage initialized successfully")
            except Exception as e:
                self.logger.warning(f"Failed to initialize Redis storage: {e}. Falling back to memory-only storage.")
                self.redis_storage = None
        
        # Determine primary storage
        if self.prefer_redis and self.redis_storage:
            self.primary_storage = self.redis_storage
            self.fallback_storage = self.memory_storage
            self.logger.info("Using Redis as primary storage with memory fallback")
        else:
            self.primary_storage = self.memory_storage
            self.fallback_storage = self.redis_storage
            self.logger.info("Using memory as primary storage with Redis fallback")
    
    @property
    def storage_type(self) -> str:
        """Get the current primary storage type."""
        if isinstance(self.primary_storage, RedisSessionStorage):
            return "redis"
        else:
            return "memory"
    
    @property
    def has_redis(self) -> bool:
        """Check if Redis storage is available."""
        return self.redis_storage is not None
    
    def generate_session_id(self) -> str:
        """
        Generate a cryptographically secure unique session ID.
        
        Returns:
            Unique session ID string
        """
        # Combine UUID4 with secure random token for extra uniqueness
        uuid_part = str(uuid.uuid4())
        random_part = secrets.token_urlsafe(16)
        timestamp = str(int(datetime.now(UTC).timestamp() * 1000))  # milliseconds
        
        # Create a hash of the combined parts for consistent length
        combined = f"{uuid_part}-{random_part}-{timestamp}"
        session_hash = hashlib.sha256(combined.encode()).hexdigest()[:32]
        
        return f"sess_{session_hash}"
    
    def generate_document_hash(self, document: Dict[str, Any]) -> str:
        """
        Generate a hash of the document for state verification.
        
        Args:
            document: JSON document to hash
            
        Returns:
            SHA-256 hash of the document
        """
        try:
            # Serialize document with sorted keys for consistent hashing
            document_json = json.dumps(document, sort_keys=True, separators=(',', ':'))
            return hashlib.sha256(document_json.encode('utf-8')).hexdigest()
        except (TypeError, ValueError) as e:
            raise SessionException(
                error_code="DOCUMENT_HASH_FAILED",
                message=f"Failed to generate document hash: {str(e)}",
                details={"error_type": type(e).__name__}
            )
    
    def create_session(
        self, 
        document: Dict[str, Any], 
        proposed_changes: List[ProposedChange]
    ) -> str:
        """
        Create a new preview session.
        
        Args:
            document: Original JSON document
            proposed_changes: List of proposed changes
            
        Returns:
            Session ID for the created session
            
        Raises:
            SessionException: If session creation fails
        """
        try:
            session_id = self.generate_session_id()
            document_hash = self.generate_document_hash(document)
            
            # Create session object
            session = PreviewSession(
                session_id=session_id,
                document=document,
                document_hash=document_hash,
                proposed_changes=proposed_changes,
                created_at=datetime.now(UTC)
            )
            
            # Try to store in primary storage first
            try:
                self.primary_storage.store_session(session_id, session, self.session_ttl)
                self.logger.debug(f"Session {session_id} stored in primary storage ({self.storage_type})")
                return session_id
            except Exception as e:
                self.logger.warning(f"Failed to store session in primary storage: {e}")
                
                # Try fallback storage if available
                if self.fallback_storage:
                    try:
                        self.fallback_storage.store_session(session_id, session, self.session_ttl)
                        self.logger.debug(f"Session {session_id} stored in fallback storage")
                        return session_id
                    except Exception as fallback_error:
                        self.logger.error(f"Failed to store session in fallback storage: {fallback_error}")
                
                # If both storages fail, raise the original error
                raise e
            
        except Exception as e:
            raise SessionException(
                error_code="SESSION_CREATION_FAILED",
                message=f"Failed to create session: {str(e)}",
                details={
                    "error_type": type(e).__name__,
                    "primary_storage": self.storage_type
                }
            )
    
    def get_session(self, session_id: str) -> PreviewSession:
        """
        Retrieve a session.
        
        Args:
            session_id: Session ID to retrieve
            
        Returns:
            PreviewSession object
            
        Raises:
            SessionException: If session retrieval fails or session not found
        """
        if not session_id or not session_id.strip():
            raise SessionException(
                error_code="INVALID_SESSION_ID",
                message="Session ID cannot be empty",
                details={"session_id": session_id}
            )
        
        session_id = session_id.strip()
        
        # Try primary storage first
        try:
            session = self.primary_storage.get_session(session_id)
            if session is not None:
                return session
        except Exception as e:
            self.logger.warning(f"Failed to retrieve session from primary storage: {e}")
        
        # Try fallback storage if available
        if self.fallback_storage:
            try:
                session = self.fallback_storage.get_session(session_id)
                if session is not None:
                    # Optionally sync back to primary storage
                    try:
                        self.primary_storage.store_session(session_id, session, self.session_ttl)
                        self.logger.debug(f"Session {session_id} synced back to primary storage")
                    except Exception:
                        pass  # Ignore sync errors
                    return session
            except Exception as e:
                self.logger.warning(f"Failed to retrieve session from fallback storage: {e}")
        
        # Session not found in any storage
        raise SessionException(
            error_code="SESSION_NOT_FOUND",
            message=f"Session not found or expired: {session_id}",
            details={
                "session_id": session_id,
                "suggestions": [
                    "Generate a new preview to create a fresh session",
                    "Check if the session ID is correct",
                    "Session may have expired - sessions are valid for 1 hour"
                ]
            }
        )
    
    def validate_session(self, session_id: str) -> bool:
        """
        Validate that a session exists and is not expired.
        
        Args:
            session_id: Session ID to validate
            
        Returns:
            True if session is valid, False otherwise
        """
        try:
            self.get_session(session_id)
            return True
        except SessionException:
            return False
    
    def verify_document_unchanged(
        self, 
        session_id: str, 
        current_document: Dict[str, Any]
    ) -> bool:
        """
        Verify that the document hasn't changed since the session was created.
        
        Args:
            session_id: Session ID to check
            current_document: Current document to verify against
            
        Returns:
            True if document is unchanged, False otherwise
            
        Raises:
            SessionException: If verification fails due to session issues
        """
        try:
            session = self.get_session(session_id)
            current_hash = self.generate_document_hash(current_document)
            
            if session.document_hash != current_hash:
                raise SessionException(
                    error_code="DOCUMENT_STATE_MISMATCH",
                    message="Document has been modified since preview was generated",
                    details={
                        "session_id": session_id,
                        "original_hash": session.document_hash,
                        "current_hash": current_hash,
                        "session_created_at": session.created_at.isoformat(),
                        "suggestions": [
                            "Generate a new preview with the current document",
                            "Ensure no other processes are modifying the document",
                            "Check if the document was manually edited"
                        ]
                    }
                )
            
            return True
            
        except SessionException:
            # Re-raise session exceptions as-is
            raise
        except Exception as e:
            raise SessionException(
                error_code="DOCUMENT_VERIFICATION_ERROR",
                message=f"Failed to verify document state: {str(e)}",
                details={
                    "session_id": session_id,
                    "error_type": type(e).__name__
                }
            )
    
    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session from both storages.
        
        Args:
            session_id: Session ID to delete
            
        Returns:
            True if session was deleted from at least one storage
        """
        if not session_id or not session_id.strip():
            return False
        
        session_id = session_id.strip()
        deleted = False
        
        # Try to delete from primary storage
        try:
            if self.primary_storage.delete_session(session_id):
                deleted = True
        except Exception as e:
            self.logger.warning(f"Failed to delete session from primary storage: {e}")
        
        # Try to delete from fallback storage
        if self.fallback_storage:
            try:
                if self.fallback_storage.delete_session(session_id):
                    deleted = True
            except Exception as e:
                self.logger.warning(f"Failed to delete session from fallback storage: {e}")
        
        return deleted
    
    def get_session_ttl(self, session_id: str) -> Optional[int]:
        """
        Get the remaining TTL for a session.
        
        Args:
            session_id: Session ID to check
            
        Returns:
            Remaining TTL in seconds, or None if session doesn't exist
        """
        if not session_id or not session_id.strip():
            return None
        
        session_id = session_id.strip()
        
        # Try primary storage first
        try:
            ttl = self.primary_storage.get_ttl(session_id)
            if ttl is not None:
                return ttl
        except Exception as e:
            self.logger.warning(f"Failed to check TTL in primary storage: {e}")
        
        # Try fallback storage
        if self.fallback_storage:
            try:
                return self.fallback_storage.get_ttl(session_id)
            except Exception as e:
                self.logger.warning(f"Failed to check TTL in fallback storage: {e}")
        
        return None
    
    def extend_session_ttl(self, session_id: str, additional_seconds: int = None) -> bool:
        """
        Extend the TTL of an existing session.
        
        Args:
            session_id: Session ID to extend
            additional_seconds: Additional seconds to add (default: reset to full TTL)
            
        Returns:
            True if TTL was extended in at least one storage
        """
        if not session_id or not session_id.strip():
            return False
        
        session_id = session_id.strip()
        new_ttl = additional_seconds if additional_seconds is not None else self.session_ttl
        extended = False
        
        # Try to extend in primary storage
        try:
            if self.primary_storage.extend_ttl(session_id, new_ttl):
                extended = True
        except Exception as e:
            self.logger.warning(f"Failed to extend TTL in primary storage: {e}")
        
        # Try to extend in fallback storage
        if self.fallback_storage:
            try:
                if self.fallback_storage.extend_ttl(session_id, new_ttl):
                    extended = True
            except Exception as e:
                self.logger.warning(f"Failed to extend TTL in fallback storage: {e}")
        
        return extended
    
    def list_active_sessions(self) -> List[str]:
        """
        List all active session IDs from both storages.
        
        Returns:
            List of active session IDs
        """
        session_ids = set()
        
        # Get sessions from primary storage
        try:
            primary_sessions = self.primary_storage.list_sessions()
            session_ids.update(primary_sessions)
        except Exception as e:
            self.logger.warning(f"Failed to list sessions from primary storage: {e}")
        
        # Get sessions from fallback storage
        if self.fallback_storage:
            try:
                fallback_sessions = self.fallback_storage.list_sessions()
                session_ids.update(fallback_sessions)
            except Exception as e:
                self.logger.warning(f"Failed to list sessions from fallback storage: {e}")
        
        return list(session_ids)
    
    def cleanup_expired_sessions(self) -> int:
        """
        Clean up expired sessions from both storages.
        
        Returns:
            Total number of sessions cleaned up
        """
        total_cleaned = 0
        
        # Cleanup primary storage
        try:
            cleaned = self.primary_storage.cleanup_expired()
            total_cleaned += cleaned
        except Exception as e:
            self.logger.warning(f"Failed to cleanup primary storage: {e}")
        
        # Cleanup fallback storage
        if self.fallback_storage:
            try:
                cleaned = self.fallback_storage.cleanup_expired()
                total_cleaned += cleaned
            except Exception as e:
                self.logger.warning(f"Failed to cleanup fallback storage: {e}")
        
        return total_cleaned
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check on the session manager.
        
        Returns:
            Health check results
        """
        health_status = {
            "status": "healthy",
            "primary_storage": self.storage_type,
            "has_redis": self.has_redis,
            "active_sessions": len(self.list_active_sessions()),
            "session_ttl": self.session_ttl,
            "storages": {}
        }
        
        # Check primary storage
        try:
            primary_health = self.primary_storage.health_check()
            health_status["storages"]["primary"] = primary_health
            if primary_health.get("status") != "healthy":
                health_status["status"] = "degraded"
        except Exception as e:
            health_status["storages"]["primary"] = {
                "status": "unhealthy",
                "error": str(e)
            }
            health_status["status"] = "degraded"
        
        # Check fallback storage
        if self.fallback_storage:
            try:
                fallback_health = self.fallback_storage.health_check()
                health_status["storages"]["fallback"] = fallback_health
            except Exception as e:
                health_status["storages"]["fallback"] = {
                    "status": "unhealthy",
                    "error": str(e)
                }
        
        return health_status
    
    def close(self):
        """Close connections to all storages."""
        try:
            self.memory_storage.close()
        except Exception as e:
            self.logger.warning(f"Error closing memory storage: {e}")
        
        if self.redis_storage:
            try:
                self.redis_storage.close()
            except Exception as e:
                self.logger.warning(f"Error closing Redis storage: {e}")