"""
Supabase client setup and configuration.
Provides singleton Supabase clients with proper error handling and authentication.
"""

import logging
from typing import Optional, Dict, Any
from functools import lru_cache

logger = logging.getLogger(__name__)

try:
    from supabase import create_client, Client
    from supabase.client import ClientOptions
    from postgrest.exceptions import APIError
    from gotrue.errors import AuthError
    SUPABASE_AVAILABLE = True
    import_error = None
except ImportError as e:
    # Handle case where supabase is not installed
    SUPABASE_AVAILABLE = False
    import_error = str(e)
    logger.error(f"Failed to import Supabase: {e}")
    
    # Create dummy classes to avoid import errors
    class Client:
        pass
    
    class ClientOptions:
        pass
    
    class AuthError(Exception):
        pass
    
    class APIError(Exception):
        pass

from .config import get_settings

logger = logging.getLogger(__name__)


class SupabaseError(Exception):
    """Custom exception for Supabase-related errors."""
    pass


class SupabaseClient:
    """
    Singleton Supabase client manager that handles both anonymous and service role clients.
    Provides efficient connection management and proper error handling.
    """
    
    _anon_client: Optional[Client] = None
    _service_client: Optional[Client] = None
    _initialized: bool = False
    
    @classmethod
    def _ensure_configuration(cls) -> Dict[str, str]:
        """
        Validate that required Supabase configuration is available.
        
        Returns:
            Dict containing validated configuration
            
        Raises:
            SupabaseError: If required configuration is missing
        """
        if not SUPABASE_AVAILABLE:
            raise SupabaseError(f"Supabase library not available: {import_error}")
            
        settings = get_settings()
        
        if not settings.supabase_url:
            raise SupabaseError("SUPABASE_URL environment variable is required")
            
        if not settings.supabase_anon_key:
            raise SupabaseError("SUPABASE_ANON_KEY environment variable is required")
            
        return {
            "url": settings.supabase_url,
            "anon_key": settings.supabase_anon_key,
            "service_key": settings.supabase_service_role_key,
        }
    
    @classmethod
    def _create_client(cls, url: str, key: str, is_service_role: bool = False) -> Client:
        """
        Create a Supabase client with appropriate configuration.
        
        Args:
            url: Supabase project URL
            key: API key (anon or service role)
            is_service_role: Whether this is a service role client
            
        Returns:
            Configured Supabase client
            
        Raises:
            SupabaseError: If client creation fails
        """
        try:
            settings = get_settings()
            
            # Log SSL configuration status
            if settings.debug:
                logger.info("Creating Supabase client in debug mode (SSL verification handled globally)")
            
            options = ClientOptions(
                auto_refresh_token=not is_service_role,  # Don't auto-refresh for service role
                persist_session=not is_service_role,     # Don't persist session for service role
            )
            
            client = create_client(url, key, options)
            
            # Test the connection with a simple query
            try:
                # This will fail gracefully if no tables exist, but will catch auth issues
                client.table("_supabase_migrations").select("*").limit(1).execute()
            except Exception as e:
                # Log the test query failure but don't raise - it's expected if no tables exist
                logger.debug(f"Test query failed (expected): {e}")
            
            logger.info(f"Successfully created {'service role' if is_service_role else 'anonymous'} Supabase client")
            return client
            
        except Exception as e:
            raise SupabaseError(f"Failed to create Supabase client: {str(e)}")
    
    @classmethod
    def initialize(cls) -> None:
        """
        Initialize Supabase clients. Should be called during application startup.
        
        Raises:
            SupabaseError: If initialization fails
        """
        if cls._initialized:
            logger.debug("Supabase clients already initialized")
            return
            
        try:
            config = cls._ensure_configuration()
            
            # Create anonymous client
            cls._anon_client = cls._create_client(
                config["url"], 
                config["anon_key"], 
                is_service_role=False
            )
            
            # Create service role client if key is provided
            if config["service_key"]:
                cls._service_client = cls._create_client(
                    config["url"], 
                    config["service_key"], 
                    is_service_role=True
                )
                logger.info("Both anonymous and service role Supabase clients initialized")
            else:
                logger.info("Anonymous Supabase client initialized (no service role key provided)")
            
            cls._initialized = True
            
        except Exception as e:
            logger.error(f"Failed to initialize Supabase clients: {e}")
            raise SupabaseError(f"Supabase initialization failed: {str(e)}")
    
    @classmethod
    def get_anon_client(cls) -> Client:
        """
        Get the anonymous Supabase client for user-facing operations.
        
        Returns:
            Anonymous Supabase client
            
        Raises:
            SupabaseError: If client is not initialized or unavailable
        """
        if not cls._initialized:
            cls.initialize()
            
        if cls._anon_client is None:
            raise SupabaseError("Anonymous Supabase client is not available")
            
        return cls._anon_client
    
    @classmethod
    def get_service_client(cls) -> Client:
        """
        Get the service role Supabase client for admin operations.
        
        Returns:
            Service role Supabase client
            
        Raises:
            SupabaseError: If client is not initialized or unavailable
        """
        if not cls._initialized:
            cls.initialize()
            
        if cls._service_client is None:
            raise SupabaseError(
                "Service role Supabase client is not available. "
                "Ensure SUPABASE_SERVICE_ROLE_KEY is configured."
            )
            
        return cls._service_client
    
    @classmethod
    def is_configured(cls) -> bool:
        """
        Check if Supabase is properly configured.
        
        Returns:
            True if Supabase can be configured, False otherwise
        """
        try:
            cls._ensure_configuration()
            return True
        except SupabaseError:
            return False
    
    @classmethod
    def health_check(cls) -> Dict[str, Any]:
        """
        Perform a health check on Supabase connections.
        
        Returns:
            Dict containing health status information
        """
        health = {
            "configured": False,
            "anon_client": False,
            "service_client": False,
            "error": None,
            "library_available": SUPABASE_AVAILABLE
        }
        
        if not SUPABASE_AVAILABLE:
            health["error"] = f"Supabase library not available: {import_error}"
            return health
        
        try:
            health["configured"] = cls.is_configured()
            
            if health["configured"]:
                # Test anonymous client
                try:
                    anon_client = cls.get_anon_client()
                    # Simple test query
                    anon_client.table("_supabase_migrations").select("*").limit(1).execute()
                    health["anon_client"] = True
                except Exception as e:
                    health["anon_client"] = False
                    logger.debug(f"Anonymous client test failed: {e}")
                
                # Test service client if available
                try:
                    service_client = cls.get_service_client()
                    # Simple test query
                    service_client.table("_supabase_migrations").select("*").limit(1).execute()
                    health["service_client"] = True
                except SupabaseError:
                    health["service_client"] = False  # Service key not configured
                except Exception as e:
                    health["service_client"] = False
                    logger.debug(f"Service client test failed: {e}")
                    
        except Exception as e:
            health["error"] = str(e)
            
        return health


# Convenience functions for direct access
@lru_cache(maxsize=1)
def get_supabase_anon() -> Client:
    """
    Get the anonymous Supabase client (cached).
    
    Returns:
        Anonymous Supabase client
    """
    return SupabaseClient.get_anon_client()


@lru_cache(maxsize=1)
def get_supabase_service() -> Client:
    """
    Get the service role Supabase client (cached).
    
    Returns:
        Service role Supabase client
    """
    return SupabaseClient.get_service_client()


def authenticate_user(email: str, password: str) -> Dict[str, Any]:
    """
    Authenticate a user with Supabase Auth.
    
    Args:
        email: User email
        password: User password
        
    Returns:
        Dict containing authentication result
        
    Raises:
        SupabaseError: If authentication fails
    """
    try:
        client = get_supabase_anon()
        response = client.auth.sign_in_with_password({
            "email": email,
            "password": password
        })
        
        if response.user:
            return {
                "success": True,
                "user": response.user,
                "session": response.session
            }
        else:
            raise SupabaseError("Authentication failed: No user returned")
            
    except AuthError as e:
        raise SupabaseError(f"Authentication failed: {str(e)}")
    except Exception as e:
        raise SupabaseError(f"Authentication error: {str(e)}")


def sign_out_user() -> bool:
    """
    Sign out the current user.
    
    Returns:
        True if sign out was successful
        
    Raises:
        SupabaseError: If sign out fails
    """
    try:
        client = get_supabase_anon()
        client.auth.sign_out()
        return True
    except Exception as e:
        raise SupabaseError(f"Sign out failed: {str(e)}")


# Initialize clients on module import if configuration is available
if SUPABASE_AVAILABLE:
    try:
        if SupabaseClient.is_configured():
            SupabaseClient.initialize()
            logger.info("Supabase clients auto-initialized on module import")
    except Exception as e:
        logger.warning(f"Failed to auto-initialize Supabase clients: {e}")
else:
    logger.info("Supabase library not available, skipping auto-initialization")