"""
Configuration loader for ytFetch
Handles both local config.yaml and Streamlit Cloud secrets
"""

import os
import yaml
import logging

logger = logging.getLogger(__name__)


def load_config():
    """
    Load configuration from st.secrets in production or config.yaml locally.
    
    Returns:
        dict: Configuration dictionary with API keys and settings
    """
    # Try Streamlit secrets first (production)
    try:
        import streamlit as st
        if hasattr(st, 'secrets') and len(st.secrets) > 0:
            logger.info("Loading config from Streamlit secrets")
            
            config = {
                "groq_api_key": st.secrets.get("groq_api_key", None),
                "openai_api_key": st.secrets.get("openai_api_key", None),
                "webshare_username": st.secrets.get("webshare_username", None),
                "webshare_password": st.secrets.get("webshare_password", None),
            }
            
            # Load performance settings if available
            if "performance" in st.secrets:
                config["performance"] = dict(st.secrets["performance"])
            
            # Load model preferences if available
            if "models" in st.secrets:
                config["models"] = dict(st.secrets["models"])
            
            # Load app config if available
            if "app_config" in st.secrets:
                config["app_config"] = dict(st.secrets["app_config"])
            
            return config
            
    except ImportError:
        # Streamlit not installed or not running in Streamlit
        pass
    except Exception as e:
        logger.warning(f"Failed to load Streamlit secrets: {e}")
    
    # Fall back to local config.yaml
    config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
    
    if os.path.exists(config_path):
        logger.info(f"Loading config from {config_path}")
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
                return config if config else {}
        except Exception as e:
            logger.error(f"Failed to load config.yaml: {e}")
            return {}
    else:
        logger.warning("No config.yaml found and not running on Streamlit Cloud")
        return {}


def get_api_key(provider: str) -> str:
    """
    Get API key for a specific provider.
    
    Args:
        provider: The provider name ('groq' or 'openai')
        
    Returns:
        str: The API key or empty string if not found
    """
    config = load_config()
    key_name = f"{provider}_api_key"
    
    # First check direct key
    if key_name in config:
        return config[key_name]
    
    # Then check environment variables as fallback
    env_key = f"{provider.upper()}_API_KEY"
    if env_key in os.environ:
        return os.environ[env_key]
    
    logger.warning(f"No API key found for {provider}")
    return ""


def get_webshare_credentials() -> tuple:
    """
    Get Webshare proxy credentials.
    
    Returns:
        tuple: (username, password) or (None, None) if not found
    """
    config = load_config()
    
    username = config.get("webshare_username")
    password = config.get("webshare_password")
    
    # Check environment variables as fallback
    if not username:
        username = os.environ.get("WEBSHARE_USERNAME")
    if not password:
        password = os.environ.get("WEBSHARE_PASSWORD")
    
    if username and password:
        logger.info("Webshare credentials found")
        return username, password
    else:
        logger.warning("No Webshare credentials found")
        return None, None


def get_performance_config() -> dict:
    """
    Get performance configuration settings.
    
    Returns:
        dict: Performance settings with defaults
    """
    config = load_config()
    
    defaults = {
        "max_concurrent_requests": 50,
        "circuit_breaker_threshold": 3,
        "http2_enabled": True,
        "rate_limit_safety_factor": 0.8,
        "max_retries": 5
    }
    
    if "performance" in config:
        defaults.update(config["performance"])
    
    return defaults


def get_model_config() -> dict:
    """
    Get model configuration preferences.
    
    Returns:
        dict: Model settings with defaults
    """
    config = load_config()
    
    defaults = {
        "default": "distil-whisper-large-v3-en",
        "fallback": "whisper-large-v3",
        "large_file_model": "whisper-large-v3-turbo"
    }
    
    if "models" in config:
        defaults.update(config["models"])
    
    return defaults