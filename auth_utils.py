# auth_utils.py
import streamlit as st
from google_auth_oauthlib.flow import Flow
import os

# This is the scope we configured in the Google Cloud Console.
SCOPES = ['https://www.googleapis.com/auth/youtube.force-ssl']
CLIENT_SECRETS_FILE = 'client_secret.json'

def get_credentials():
    """
    Manages the OAuth2 flow and returns user credentials.
    - Checks session_state for existing credentials.
    - If none, starts the OAuth2 flow.
    - Handles the redirect from Google.
    - Stores credentials in session_state.
    """
    print("--- DEBUG: get_credentials() called. ---")
    
    # 1. Check if credentials already exist in the session.
    if 'credentials' in st.session_state and st.session_state['credentials']:
        print("--- DEBUG: Found existing credentials in session state. Returning them. ---")
        return st.session_state['credentials']

    # 2. Check for the authorization code in the URL query params.
    # This is how Google sends the user back to us.
    auth_code = st.query_params.get('code')
    if not auth_code:
        print("--- DEBUG: No auth_code in URL. Trying to create a new flow. ---")
        try:
            # Check if the secrets file exists BEFORE trying to use it
            if not os.path.exists(CLIENT_SECRETS_FILE):
                error_msg = f"CRITICAL ERROR: The secrets file '{CLIENT_SECRETS_FILE}' was not found."
                print(f"--- DEBUG: {error_msg} ---")
                st.error(error_msg)
                st.error(f"Current working directory is: {os.getcwd()}")
                return None

            print(f"--- DEBUG: Found '{CLIENT_SECRETS_FILE}'. Attempting to create Flow object. ---")
            # 3. If no code, start the authorization flow.
            flow = Flow.from_client_secrets_file(CLIENT_SECRETS_FILE, scopes=SCOPES)
            # Use http://localhost:8501 for local development.
            # This must match one of the URIs you configured in the console.
            flow.redirect_uri = 'http://localhost:8501' 
            
            authorization_url, state = flow.authorization_url(
                access_type='offline',
                include_granted_scopes='true'
            )
            # Store the flow and state in session to retrieve after redirect
            st.session_state['flow'] = flow
            st.session_state['state'] = state
            
            print("--- DEBUG: Successfully created authorization URL. Returning URL. ---")
            # Return the URL for the login button
            return authorization_url
        except Exception as e:
            # This will catch any error during Flow creation
            error_msg = f"CRITICAL ERROR creating OAuth flow: {e}"
            print(f"--- DEBUG: {error_msg} ---")
            st.error(error_msg)
            return None
    else:
        # 4. If there is a code, exchange it for tokens.
        print("--- DEBUG: Found auth_code in URL. Exchanging for tokens. ---")
        flow = st.session_state.get('flow')
        print(f"--- DEBUG: Retrieved flow from session state: {flow is not None} ---")
        
        if not flow:
            print("--- DEBUG: Flow is missing, recreating from client secrets ---")
            # If the flow is missing, recreate it (this can happen due to Streamlit session issues)
            try:
                flow = Flow.from_client_secrets_file(CLIENT_SECRETS_FILE, scopes=SCOPES)
                flow.redirect_uri = 'http://localhost:8501'
                print("--- DEBUG: Successfully recreated flow object ---")
            except Exception as e:
                error_msg = f"Failed to recreate OAuth flow: {e}"
                print(f"--- DEBUG: {error_msg} ---")
                st.error(error_msg)
                return None

        try:
            print("--- DEBUG: Attempting to fetch token with auth code ---")
            # Exchange the authorization code for credentials
            flow.fetch_token(code=auth_code)
            credentials = flow.credentials
            st.session_state['credentials'] = credentials # Store credentials
            
            # Clean up session state and URL
            if 'flow' in st.session_state:
                del st.session_state['flow']
            if 'state' in st.session_state:
                del st.session_state['state']
            st.query_params.clear() # Remove code from URL
            
            print("--- DEBUG: Token exchange successful. ---")
            return credentials
        except Exception as e:
            error_msg = f"Error fetching token: {e}"
            print(f"--- DEBUG: {error_msg} ---")
            st.error(error_msg)
            return None