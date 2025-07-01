"""
ytFetch Backend - FastAPI Application

Production-ready YouTube transcription service with enhanced download strategies
and AI-powered audio transcription.
"""

__version__ = "0.1.0"

# Configure SSL for development environment
import os
import ssl
import warnings

# Check if we're in development mode
if os.getenv("DEBUG", "false").lower() == "true":
    # Disable SSL certificate verification for development
    # This is necessary when connecting to Supabase in local development
    # WARNING: This should NEVER be used in production!
    
    # Set environment variables to disable SSL verification
    os.environ['PYTHONHTTPSVERIFY'] = '0'
    os.environ['REQUESTS_CA_BUNDLE'] = ''
    os.environ['CURL_CA_BUNDLE'] = ''
    
    # Disable SSL warnings
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    # Create unverified SSL context as default
    ssl._create_default_https_context = ssl._create_unverified_context
    
    # Also set httpx to not verify SSL
    try:
        import httpx
        # Set httpx default verify to False
        import httpx._config
        httpx._config.DEFAULT_TIMEOUT_CONFIG = httpx.Timeout(timeout=30.0)
        
        # Monkey patch httpx Client to default verify=False in debug mode
        _original_httpx_client_init = httpx.Client.__init__
        
        def _patched_httpx_client_init(self, *args, **kwargs):
            if 'verify' not in kwargs:
                kwargs['verify'] = False
            _original_httpx_client_init(self, *args, **kwargs)
        
        httpx.Client.__init__ = _patched_httpx_client_init
        
        # Same for AsyncClient
        _original_httpx_async_client_init = httpx.AsyncClient.__init__
        
        def _patched_httpx_async_client_init(self, *args, **kwargs):
            if 'verify' not in kwargs:
                kwargs['verify'] = False
            _original_httpx_async_client_init(self, *args, **kwargs)
        
        httpx.AsyncClient.__init__ = _patched_httpx_async_client_init
        
    except ImportError:
        pass
    
    warnings.warn(
        "SSL certificate verification is disabled. This is only safe in development!",
        RuntimeWarning
    )