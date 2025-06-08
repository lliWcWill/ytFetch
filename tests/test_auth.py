"""Functional unit tests for auth_utils module."""
import pytest
from unittest.mock import Mock
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_returns_existing_credentials_from_session():
    """Test that existing credentials in session are returned."""
    from unittest.mock import patch
    
    mock_creds = Mock()
    with patch('auth_utils.st') as mock_st:
        mock_st.session_state = {'credentials': mock_creds}
        
        from auth_utils import get_credentials
        result = get_credentials()
        
        assert result == mock_creds


def test_starts_oauth_flow_when_no_auth_code():
    """Test that OAuth flow starts when no auth code is present."""
    from unittest.mock import patch, Mock
    
    with patch('auth_utils.st') as mock_st, \
         patch('auth_utils.Flow') as mock_flow_class:
        
        # Setup mocks
        mock_st.session_state = {}
        mock_st.query_params.get.return_value = None
        
        mock_flow = Mock()
        mock_flow.authorization_url.return_value = ("https://auth.url", "state123")
        mock_flow_class.from_client_secrets_file.return_value = mock_flow
        
        from auth_utils import get_credentials
        result = get_credentials()
        
        assert result == "https://auth.url"
        assert mock_st.session_state['flow'] == mock_flow
        assert mock_st.session_state['state'] == "state123"


def test_successful_token_exchange():
    """Test successful exchange of auth code for credentials."""
    from unittest.mock import patch, Mock
    
    with patch('auth_utils.st') as mock_st:
        # Create a mock flow and credentials
        mock_flow = Mock()
        mock_creds = Mock()
        mock_flow.credentials = mock_creds
        
        # Setup session state and query params
        session_state = {'flow': mock_flow, 'state': 'test_state'}  # Flow and state exist
        mock_st.session_state = session_state
        mock_st.query_params.get.return_value = "auth_code_123"
        mock_st.query_params.clear = Mock()
        
        from auth_utils import get_credentials
        result = get_credentials()
        
        # Verify the flow
        mock_flow.fetch_token.assert_called_once_with(code="auth_code_123")
        mock_st.query_params.clear.assert_called_once()
        assert result == mock_creds
        assert session_state['credentials'] == mock_creds


def test_missing_flow_in_session():
    """Test error when auth code exists but flow is missing."""
    from unittest.mock import patch, Mock
    
    with patch('auth_utils.st') as mock_st:
        mock_st.session_state = {}  # No flow
        mock_st.query_params.get.return_value = "auth_code_123"
        mock_st.error = Mock()
        
        from auth_utils import get_credentials
        result = get_credentials()
        
        assert result is None
        mock_st.error.assert_called_once()


def test_token_exchange_exception():
    """Test handling of token exchange exceptions."""
    from unittest.mock import patch, Mock
    
    with patch('auth_utils.st') as mock_st:
        # Mock flow that raises exception
        mock_flow = Mock()
        mock_flow.fetch_token.side_effect = Exception("Network error")
        
        session_state = {'flow': mock_flow}
        mock_st.session_state = session_state
        mock_st.query_params.get.return_value = "auth_code_123"
        mock_st.error = Mock()
        
        from auth_utils import get_credentials
        result = get_credentials()
        
        assert result is None
        mock_st.error.assert_called_once()
        error_call_args = mock_st.error.call_args[0][0]
        assert "Network error" in error_call_args


def test_file_not_found_exception():
    """Test handling when client secrets file is missing."""
    from unittest.mock import patch
    
    with patch('auth_utils.st') as mock_st, \
         patch('auth_utils.Flow') as mock_flow_class:
        
        mock_st.session_state = {}
        mock_st.query_params.get.return_value = None
        mock_flow_class.from_client_secrets_file.side_effect = FileNotFoundError()
        
        from auth_utils import get_credentials
        
        # Should raise the FileNotFoundError
        with pytest.raises(FileNotFoundError):
            get_credentials()