"""Session manager for Redis-based session storage."""

import hashlib
import json
import secrets
import uuid
from datetime import datetime, UTC
from typing import Any, Dict, List, Optional

import redis
from redis.exceptions import ConnectionError, TimeoutError, RedisError

from ..config.models import RedisConfig
from ..models.core import ProposedChange
from ..models.session import PreviewSession
from ..models.errors import SessionError, SessionException


class SessionManager:
    """Manages preview sessions using Redis storage."""
    
    def __init__(self, redis_config: RedisConfig, session_ttl: int = 3600):
        """
        Initialize the session manager.
        
        Args:
            redis_config: Redis configuration
            session_ttl: Session time-to-live in seconds (default: 1 hour)
        """
        self.redis_config = redis_config
        self.session_ttl = session_ttl
        self._redis_client: Optional[redis.Redis] = None
        self._session_key_prefix = "json_editor_session:"
    
    @property
    def redis_client(self) -> redis.Redis:
        """Get or create Redis client with connection pooling."""
        if self._redis_client is None:
            try:
                self._redis_client = redis.Redis(
                    host=self.redis_config.host,
                    port=self.redis_config.port,
                    password=self.redis_config.password,
                    db=self.redis_config.db,
                    socket_timeout=self.redis_config.socket_timeout,
                    socket_connect_timeout=self.redis_config.connection_timeout,
                    max_connections=self.redis_config.max_connections,
                    decode_responses=True,
                    retry_on_timeout=True,
                    health_check_interval=30
                )
                # Test the connection
                self._redis_client.ping()
            except (ConnectionError, TimeoutError) as e:
                raise SessionException(
                    error_code="REDIS_CONNECTION_FAILED",
                    message=f"Failed to connect to Redis server: {str(e)}",
                    details={
                        "host": self.redis_config.host,
                        "port": self.redis_config.port,
                        "db": self.redis_config.db
                    }
                )
            except Exception as e:
                raise SessionException(
                    error_code="REDIS_INITIALIZATION_FAILED",
                    message=f"Failed to initialize Redis client: {str(e)}",
                    details={"error_type": type(e).__name__}
                )
        
        return self._redis_client
    
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
        Create a new preview session in Redis.
        
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
            
            # Store in Redis with TTL
            redis_key = f"{self._session_key_prefix}{session_id}"
            session_data = session.model_dump_json()
            
            # Use pipeline for atomic operation
            pipe = self.redis_client.pipeline()
            pipe.setex(redis_key, self.session_ttl, session_data)
            pipe.execute()
            
            return session_id
            
        except RedisError as e:
            raise SessionException(
                error_code="SESSION_CREATION_FAILED",
                message=f"Failed to create session in Redis: {str(e)}",
                details={
                    "redis_error": str(e),
                    "error_type": type(e).__name__
                }
            )
        except Exception as e:
            raise SessionException(
                error_code="SESSION_CREATION_ERROR",
                message=f"Unexpected error during session creation: {str(e)}",
                details={
                    "error_type": type(e).__name__,
                    "session_id": session_id if 'session_id' in locals() else None
                }
            )
    
    def get_session(self, session_id: str) -> PreviewSession:
        """
        Retrieve a session from Redis.
        
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
        
        try:
            redis_key = f"{self._session_key_prefix}{session_id.strip()}"
            session_data = self.redis_client.get(redis_key)
            
            if session_data is None:
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
            
            # Parse session data
            session = PreviewSession.model_validate_json(session_data)
            return session
            
        except SessionException:
            # Re-raise session exceptions as-is
            raise
        except RedisError as e:
            raise SessionException(
                error_code="SESSION_RETRIEVAL_FAILED",
                message=f"Failed to retrieve session from Redis: {str(e)}",
                details={
                    "session_id": session_id,
                    "redis_error": str(e),
                    "error_type": type(e).__name__
                }
            )
        except (ValueError, TypeError) as e:
            raise SessionException(
                error_code="SESSION_DATA_CORRUPTED",
                message=f"Session data is corrupted or invalid: {str(e)}",
                details={
                    "session_id": session_id,
                    "error_type": type(e).__name__,
                    "suggestions": ["Generate a new preview to create a fresh session"]
                }
            )
        except Exception as e:
            raise SessionException(
                error_code="SESSION_RETRIEVAL_ERROR",
                message=f"Unexpected error during session retrieval: {str(e)}",
                details={
                    "session_id": session_id,
                    "error_type": type(e).__name__
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
        Delete a session from Redis.
        
        Args:
            session_id: Session ID to delete
            
        Returns:
            True if session was deleted, False if session didn't exist
            
        Raises:
            SessionException: If deletion fails due to Redis errors
        """
        if not session_id or not session_id.strip():
            return False
        
        try:
            redis_key = f"{self._session_key_prefix}{session_id.strip()}"
            deleted_count = self.redis_client.delete(redis_key)
            return deleted_count > 0
            
        except RedisError as e:
            raise SessionException(
                error_code="SESSION_DELETION_FAILED",
                message=f"Failed to delete session from Redis: {str(e)}",
                details={
                    "session_id": session_id,
                    "redis_error": str(e),
                    "error_type": type(e).__name__
                }
            )
        except Exception as e:
            raise SessionException(
                error_code="SESSION_DELETION_ERROR",
                message=f"Unexpected error during session deletion: {str(e)}",
                details={
                    "session_id": session_id,
                    "error_type": type(e).__name__
                }
            )
    
    def get_session_ttl(self, session_id: str) -> Optional[int]:
        """
        Get the remaining TTL for a session.
        
        Args:
            session_id: Session ID to check
            
        Returns:
            Remaining TTL in seconds, or None if session doesn't exist
            
        Raises:
            SessionException: If TTL check fails due to Redis errors
        """
        if not session_id or not session_id.strip():
            return None
        
        try:
            redis_key = f"{self._session_key_prefix}{session_id.strip()}"
            ttl = self.redis_client.ttl(redis_key)
            
            # TTL returns -2 if key doesn't exist, -1 if key exists but has no TTL
            if ttl == -2:
                return None  # Session doesn't exist
            elif ttl == -1:
                return self.session_ttl  # Key exists but no TTL set (shouldn't happen)
            else:
                return ttl  # Remaining TTL in seconds
                
        except RedisError as e:
            raise SessionException(
                error_code="SESSION_TTL_CHECK_FAILED",
                message=f"Failed to check session TTL: {str(e)}",
                details={
                    "session_id": session_id,
                    "redis_error": str(e),
                    "error_type": type(e).__name__
                }
            )
        except Exception as e:
            raise SessionException(
                error_code="SESSION_TTL_ERROR",
                message=f"Unexpected error during TTL check: {str(e)}",
                details={
                    "session_id": session_id,
                    "error_type": type(e).__name__
                }
            )
    
    def extend_session_ttl(self, session_id: str, additional_seconds: int = None) -> bool:
        """
        Extend the TTL of an existing session.
        
        Args:
            session_id: Session ID to extend
            additional_seconds: Additional seconds to add (default: reset to full TTL)
            
        Returns:
            True if TTL was extended, False if session doesn't exist
            
        Raises:
            SessionException: If TTL extension fails
        """
        if not session_id or not session_id.strip():
            return False
        
        try:
            redis_key = f"{self._session_key_prefix}{session_id.strip()}"
            
            # Check if session exists
            if not self.redis_client.exists(redis_key):
                return False
            
            # Set new TTL
            new_ttl = additional_seconds if additional_seconds is not None else self.session_ttl
            success = self.redis_client.expire(redis_key, new_ttl)
            return success
            
        except RedisError as e:
            raise SessionException(
                error_code="SESSION_TTL_EXTENSION_FAILED",
                message=f"Failed to extend session TTL: {str(e)}",
                details={
                    "session_id": session_id,
                    "additional_seconds": additional_seconds,
                    "redis_error": str(e),
                    "error_type": type(e).__name__
                }
            )
        except Exception as e:
            raise SessionException(
                error_code="SESSION_TTL_EXTENSION_ERROR",
                message=f"Unexpected error during TTL extension: {str(e)}",
                details={
                    "session_id": session_id,
                    "additional_seconds": additional_seconds,
                    "error_type": type(e).__name__
                }
            )
    
    def list_active_sessions(self) -> List[str]:
        """
        List all active session IDs.
        
        Returns:
            List of active session IDs
            
        Raises:
            SessionException: If listing fails due to Redis errors
        """
        try:
            pattern = f"{self._session_key_prefix}*"
            keys = self.redis_client.keys(pattern)
            
            # Extract session IDs from Redis keys
            session_ids = []
            for key in keys:
                if key.startswith(self._session_key_prefix):
                    session_id = key[len(self._session_key_prefix):]
                    session_ids.append(session_id)
            
            return session_ids
            
        except RedisError as e:
            raise SessionException(
                error_code="SESSION_LISTING_FAILED",
                message=f"Failed to list active sessions: {str(e)}",
                details={
                    "redis_error": str(e),
                    "error_type": type(e).__name__
                }
            )
        except Exception as e:
            raise SessionException(
                error_code="SESSION_LISTING_ERROR",
                message=f"Unexpected error during session listing: {str(e)}",
                details={"error_type": type(e).__name__}
            )
    
    def cleanup_expired_sessions(self) -> int:
        """
        Clean up expired sessions (Redis handles this automatically, but this provides manual cleanup).
        
        Returns:
            Number of sessions cleaned up
            
        Note:
            Redis automatically removes expired keys, so this is mainly for manual cleanup
            or getting statistics about expired sessions.
        """
        try:
            active_sessions = self.list_active_sessions()
            initial_count = len(active_sessions)
            
            # Check each session and remove any that are expired or corrupted
            cleaned_count = 0
            for session_id in active_sessions:
                try:
                    # Try to get the session - this will fail if expired or corrupted
                    self.get_session(session_id)
                except SessionException:
                    # Session is expired or corrupted, delete it
                    if self.delete_session(session_id):
                        cleaned_count += 1
            
            return cleaned_count
            
        except Exception as e:
            raise SessionException(
                error_code="SESSION_CLEANUP_ERROR",
                message=f"Failed to cleanup expired sessions: {str(e)}",
                details={"error_type": type(e).__name__}
            )
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check on the session manager.
        
        Returns:
            Health check results
            
        Raises:
            SessionException: If health check fails
        """
        try:
            # Test Redis connection
            ping_result = self.redis_client.ping()
            
            # Get Redis info
            redis_info = self.redis_client.info()
            
            # Count active sessions
            active_sessions = len(self.list_active_sessions())
            
            return {
                "status": "healthy",
                "redis_connected": ping_result,
                "redis_version": redis_info.get("redis_version", "unknown"),
                "active_sessions": active_sessions,
                "session_ttl": self.session_ttl,
                "redis_config": {
                    "host": self.redis_config.host,
                    "port": self.redis_config.port,
                    "db": self.redis_config.db
                }
            }
            
        except Exception as e:
            raise SessionException(
                error_code="HEALTH_CHECK_FAILED",
                message=f"Session manager health check failed: {str(e)}",
                details={"error_type": type(e).__name__}
            )
    
    def close(self):
        """Close the Redis connection."""
        if self._redis_client is not None:
            try:
                self._redis_client.close()
            except Exception:
                pass  # Ignore errors during cleanup
            finally:
                self._redis_client = None