"""Session storage interfaces and implementations."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING
import threading
import time

if TYPE_CHECKING:
    import redis
    from redis.exceptions import RedisError
else:
    try:
        import redis
        from redis.exceptions import ConnectionError, TimeoutError, RedisError
        REDIS_AVAILABLE = True
    except ImportError:
        REDIS_AVAILABLE = False
        # Define placeholder types for when Redis is not available
        class RedisError(Exception):
            pass
        class ConnectionError(RedisError):
            pass
        class TimeoutError(RedisError):
            pass
        redis = None

from ..config.models import RedisConfig
from ..models.session import PreviewSession
from ..models.errors import SessionException


class SessionStorageInterface(ABC):
    """Abstract interface for session storage implementations."""
    
    @abstractmethod
    def store_session(self, session_id: str, session: PreviewSession, ttl: int) -> None:
        """Store a session with TTL."""
        pass
    
    @abstractmethod
    def get_session(self, session_id: str) -> Optional[PreviewSession]:
        """Retrieve a session by ID."""
        pass
    
    @abstractmethod
    def delete_session(self, session_id: str) -> bool:
        """Delete a session. Returns True if session existed."""
        pass
    
    @abstractmethod
    def exists(self, session_id: str) -> bool:
        """Check if a session exists."""
        pass
    
    @abstractmethod
    def get_ttl(self, session_id: str) -> Optional[int]:
        """Get remaining TTL for a session. Returns None if session doesn't exist."""
        pass
    
    @abstractmethod
    def extend_ttl(self, session_id: str, additional_seconds: int) -> bool:
        """Extend TTL for a session. Returns True if successful."""
        pass
    
    @abstractmethod
    def list_sessions(self) -> List[str]:
        """List all active session IDs."""
        pass
    
    @abstractmethod
    def cleanup_expired(self) -> int:
        """Clean up expired sessions. Returns number of sessions cleaned."""
        pass
    
    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """Perform health check on the storage."""
        pass
    
    @abstractmethod
    def close(self) -> None:
        """Close the storage connection."""
        pass


class InMemorySessionStorage(SessionStorageInterface):
    """In-memory session storage implementation."""
    
    def __init__(self):
        """Initialize in-memory storage."""
        self._sessions: Dict[str, Tuple[PreviewSession, float]] = {}  # session_id -> (session, expiry_time)
        self._lock = threading.RLock()
        self._cleanup_interval = 300  # 5 minutes
        self._last_cleanup = time.time()
    
    def _cleanup_if_needed(self) -> None:
        """Clean up expired sessions if needed."""
        current_time = time.time()
        if current_time - self._last_cleanup > self._cleanup_interval:
            self.cleanup_expired()
            self._last_cleanup = current_time
    
    def _is_expired(self, expiry_time: float) -> bool:
        """Check if a session is expired."""
        return time.time() > expiry_time
    
    def store_session(self, session_id: str, session: PreviewSession, ttl: int) -> None:
        """Store a session with TTL."""
        with self._lock:
            expiry_time = time.time() + ttl
            self._sessions[session_id] = (session, expiry_time)
            self._cleanup_if_needed()
    
    def get_session(self, session_id: str) -> Optional[PreviewSession]:
        """Retrieve a session by ID."""
        with self._lock:
            self._cleanup_if_needed()
            
            if session_id not in self._sessions:
                return None
            
            session, expiry_time = self._sessions[session_id]
            
            if self._is_expired(expiry_time):
                del self._sessions[session_id]
                return None
            
            return session
    
    def delete_session(self, session_id: str) -> bool:
        """Delete a session. Returns True if session existed."""
        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                return True
            return False
    
    def exists(self, session_id: str) -> bool:
        """Check if a session exists."""
        with self._lock:
            self._cleanup_if_needed()
            
            if session_id not in self._sessions:
                return False
            
            _, expiry_time = self._sessions[session_id]
            
            if self._is_expired(expiry_time):
                del self._sessions[session_id]
                return False
            
            return True
    
    def get_ttl(self, session_id: str) -> Optional[int]:
        """Get remaining TTL for a session. Returns None if session doesn't exist."""
        with self._lock:
            self._cleanup_if_needed()
            
            if session_id not in self._sessions:
                return None
            
            _, expiry_time = self._sessions[session_id]
            
            if self._is_expired(expiry_time):
                del self._sessions[session_id]
                return None
            
            remaining_seconds = int(expiry_time - time.time())
            return max(0, remaining_seconds)
    
    def extend_ttl(self, session_id: str, additional_seconds: int) -> bool:
        """Extend TTL for a session. Returns True if successful."""
        with self._lock:
            self._cleanup_if_needed()
            
            if session_id not in self._sessions:
                return False
            
            session, expiry_time = self._sessions[session_id]
            
            if self._is_expired(expiry_time):
                del self._sessions[session_id]
                return False
            
            new_expiry = expiry_time + additional_seconds
            self._sessions[session_id] = (session, new_expiry)
            return True
    
    def list_sessions(self) -> List[str]:
        """List all active session IDs."""
        with self._lock:
            self._cleanup_if_needed()
            current_time = time.time()
            
            active_sessions = []
            expired_sessions = []
            
            for session_id, (_, expiry_time) in self._sessions.items():
                if expiry_time > current_time:
                    active_sessions.append(session_id)
                else:
                    expired_sessions.append(session_id)
            
            # Clean up expired sessions
            for session_id in expired_sessions:
                del self._sessions[session_id]
            
            return active_sessions
    
    def cleanup_expired(self) -> int:
        """Clean up expired sessions. Returns number of sessions cleaned."""
        with self._lock:
            current_time = time.time()
            expired_sessions = []
            
            for session_id, (_, expiry_time) in self._sessions.items():
                if expiry_time <= current_time:
                    expired_sessions.append(session_id)
            
            for session_id in expired_sessions:
                del self._sessions[session_id]
            
            return len(expired_sessions)
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check on the storage."""
        with self._lock:
            active_sessions = len(self.list_sessions())
            
            return {
                "status": "healthy",
                "storage_type": "in_memory",
                "active_sessions": active_sessions,
                "total_stored_sessions": len(self._sessions),
                "memory_usage_estimate": f"{len(self._sessions) * 1024}B"  # rough estimate
            }
    
    def close(self) -> None:
        """Close the storage connection."""
        with self._lock:
            self._sessions.clear()


class RedisSessionStorage(SessionStorageInterface):
    """Redis-based session storage implementation."""
    
    def __init__(self, redis_config: RedisConfig):
        """Initialize Redis storage."""
        self.redis_config = redis_config
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
                # Test connection
                self._redis_client.ping()
            except (ConnectionError, TimeoutError) as e:
                raise SessionException(
                    error_code="REDIS_CONNECTION_FAILED",
                    message=f"Failed to connect to Redis: {str(e)}",
                    details={
                        "host": self.redis_config.host,
                        "port": self.redis_config.port,
                        "error": str(e)
                    }
                )
            except Exception as e:
                raise SessionException(
                    error_code="REDIS_INITIALIZATION_FAILED",
                    message=f"Failed to initialize Redis client: {str(e)}",
                    details={"error": str(e)}
                )
        
        return self._redis_client
    
    def store_session(self, session_id: str, session: PreviewSession, ttl: int) -> None:
        """Store a session with TTL."""
        try:
            redis_key = f"{self._session_key_prefix}{session_id}"
            session_data = session.model_dump_json()
            
            # Use pipeline for atomic operation
            pipe = self.redis_client.pipeline()
            pipe.setex(redis_key, ttl, session_data)
            pipe.execute()
            
        except RedisError as e:
            raise SessionException(
                error_code="SESSION_STORAGE_FAILED",
                message=f"Failed to store session in Redis: {str(e)}",
                details={
                    "session_id": session_id,
                    "redis_error": str(e),
                    "error_type": type(e).__name__
                }
            )
    
    def get_session(self, session_id: str) -> Optional[PreviewSession]:
        """Retrieve a session by ID."""
        try:
            redis_key = f"{self._session_key_prefix}{session_id}"
            session_data: Any = self.redis_client.get(redis_key)
            
            if session_data is None:
                return None
            
            # Parse session data
            session = PreviewSession.model_validate_json(str(session_data))
            return session
            
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
                    "error_type": type(e).__name__
                }
            )
    
    def delete_session(self, session_id: str) -> bool:
        """Delete a session. Returns True if session existed."""
        try:
            redis_key = f"{self._session_key_prefix}{session_id}"
            deleted_count: Any = self.redis_client.delete(redis_key)
            return int(deleted_count) > 0
            
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
    
    def exists(self, session_id: str) -> bool:
        """Check if a session exists."""
        try:
            redis_key = f"{self._session_key_prefix}{session_id}"
            exists_result: Any = self.redis_client.exists(redis_key)
            return int(exists_result) > 0
        except RedisError as e:
            raise SessionException(
                error_code="SESSION_EXISTS_CHECK_FAILED",
                message=f"Failed to check session existence: {str(e)}",
                details={
                    "session_id": session_id,
                    "redis_error": str(e)
                }
            )
    
    def get_ttl(self, session_id: str) -> Optional[int]:
        """Get remaining TTL for a session. Returns None if session doesn't exist."""
        try:
            redis_key = f"{self._session_key_prefix}{session_id}"
            ttl: Any = self.redis_client.ttl(redis_key)
            
            # TTL returns -2 if key doesn't exist, -1 if key exists but has no TTL
            ttl_int = int(ttl)
            if ttl_int == -2:
                return None
            elif ttl_int == -1:
                return None  # Should not happen with our setup
            else:
                return ttl_int
                
        except RedisError as e:
            raise SessionException(
                error_code="SESSION_TTL_CHECK_FAILED",
                message=f"Failed to check session TTL: {str(e)}",
                details={
                    "session_id": session_id,
                    "redis_error": str(e)
                }
            )
    
    def extend_ttl(self, session_id: str, additional_seconds: int) -> bool:
        """Extend TTL for a session. Returns True if successful."""
        try:
            redis_key = f"{self._session_key_prefix}{session_id}"
            
            # Check if session exists
            if not self.redis_client.exists(redis_key):
                return False
            
            # Extend TTL
            success: Any = self.redis_client.expire(redis_key, additional_seconds)
            return bool(success)
            
        except RedisError as e:
            raise SessionException(
                error_code="SESSION_TTL_EXTENSION_FAILED",
                message=f"Failed to extend session TTL: {str(e)}",
                details={
                    "session_id": session_id,
                    "additional_seconds": additional_seconds,
                    "redis_error": str(e)
                }
            )
    
    def list_sessions(self) -> List[str]:
        """List all active session IDs."""
        try:
            pattern = f"{self._session_key_prefix}*"
            keys: Any = self.redis_client.keys(pattern)
            
            # Extract session IDs from Redis keys
            session_ids = []
            for key in list(keys):
                key_str = str(key)
                if key_str.startswith(self._session_key_prefix):
                    session_ids.append(key_str[len(self._session_key_prefix):])
            
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
    
    def cleanup_expired(self) -> int:
        """Clean up expired sessions. Returns number of sessions cleaned."""
        # Redis automatically removes expired keys, so this is mainly for statistics
        try:
            active_sessions = self.list_sessions()
            
            # Check each session and remove any that are expired or corrupted
            cleaned_count = 0
            for session_id in active_sessions:
                try:
                    if not self.exists(session_id):
                        cleaned_count += 1
                except Exception:
                    # Session might be corrupted, try to delete it
                    self.delete_session(session_id)
                    cleaned_count += 1
            
            return cleaned_count
            
        except Exception as e:
            raise SessionException(
                error_code="SESSION_CLEANUP_ERROR",
                message=f"Failed to cleanup expired sessions: {str(e)}",
                details={"error_type": type(e).__name__}
            )
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check on the storage."""
        try:
            # Test Redis connection
            ping_result: Any = self.redis_client.ping()
            
            # Get Redis info
            redis_info: Any = self.redis_client.info()
            
            # Count active sessions
            active_sessions = len(self.list_sessions())
            
            return {
                "status": "healthy",
                "storage_type": "redis",
                "redis_connected": bool(ping_result),
                "redis_version": dict(redis_info).get("redis_version", "unknown"),
                "active_sessions": active_sessions,
                "redis_config": {
                    "host": self.redis_config.host,
                    "port": self.redis_config.port,
                    "db": self.redis_config.db
                }
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "storage_type": "redis",
                "error": str(e)
            }
    
    def close(self) -> None:
        """Close the Redis connection."""
        if self._redis_client is not None:
            try:
                self._redis_client.close()
            except Exception:
                pass  # Ignore close errors
            finally:
                self._redis_client = None