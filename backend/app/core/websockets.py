"""
WebSocket Connection Manager for ytFetch application.

This module provides a thread-safe ConnectionManager class for handling
WebSocket connections, client management, and progress updates.
"""

import asyncio
import logging
import threading
from typing import Dict, Optional
from fastapi import WebSocket, WebSocketDisconnect
import json

# Configure logging
logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Thread-safe WebSocket connection manager for handling multiple client connections.
    
    This class manages WebSocket connections, provides methods for connecting/disconnecting
    clients, and sending progress updates to specific clients.
    """
    
    def __init__(self):
        """Initialize the connection manager with empty connections and thread lock."""
        self.active_connections: Dict[str, WebSocket] = {}
        self._lock = threading.RLock()  # Reentrant lock for thread safety
        
    async def connect(self, websocket: WebSocket, client_id: str) -> None:
        """
        Accept a WebSocket connection and add it to active connections.
        
        Args:
            websocket: The WebSocket connection object
            client_id: Unique identifier for the client
            
        Raises:
            Exception: If connection acceptance fails
        """
        try:
            await websocket.accept()
            
            with self._lock:
                # Disconnect existing connection with same client_id if exists
                if client_id in self.active_connections:
                    logger.warning(f"Client {client_id} already connected. Replacing existing connection.")
                    await self._force_disconnect(client_id)
                
                self.active_connections[client_id] = websocket
                
            logger.info(f"Client {client_id} connected successfully. Total connections: {len(self.active_connections)}")
            
        except Exception as e:
            logger.error(f"Failed to connect client {client_id}: {str(e)}")
            raise
    
    async def disconnect(self, client_id: str) -> None:
        """
        Disconnect a client and remove from active connections.
        
        Args:
            client_id: Unique identifier for the client to disconnect
        """
        with self._lock:
            if client_id in self.active_connections:
                websocket = self.active_connections[client_id]
                del self.active_connections[client_id]
                
                try:
                    # Attempt graceful close
                    await websocket.close()
                except Exception as e:
                    logger.warning(f"Error closing WebSocket for client {client_id}: {str(e)}")
                
                logger.info(f"Client {client_id} disconnected. Total connections: {len(self.active_connections)}")
            else:
                logger.warning(f"Attempted to disconnect non-existent client: {client_id}")
    
    async def _force_disconnect(self, client_id: str) -> None:
        """
        Force disconnect a client without acquiring lock (internal use only).
        
        Args:
            client_id: Unique identifier for the client to disconnect
        """
        if client_id in self.active_connections:
            websocket = self.active_connections[client_id]
            del self.active_connections[client_id]
            
            try:
                await websocket.close()
            except Exception as e:
                logger.warning(f"Error force closing WebSocket for client {client_id}: {str(e)}")
    
    async def send_progress(self, client_id: str, message: dict) -> bool:
        """
        Send a progress message to a specific client.
        
        Args:
            client_id: Unique identifier for the target client
            message: Dictionary containing the message data
            
        Returns:
            bool: True if message sent successfully, False otherwise
        """
        with self._lock:
            if client_id not in self.active_connections:
                logger.warning(f"Cannot send message to non-existent client: {client_id}")
                return False
            
            websocket = self.active_connections[client_id]
        
        try:
            # Ensure message is properly formatted
            if not isinstance(message, dict):
                logger.error(f"Message must be a dictionary, got {type(message)}")
                return False
            
            # Add timestamp if not present
            if 'timestamp' not in message:
                import time
                message['timestamp'] = time.time()
            
            # Send the message
            await websocket.send_text(json.dumps(message))
            logger.debug(f"Progress message sent to client {client_id}: {message}")
            return True
            
        except WebSocketDisconnect:
            logger.info(f"Client {client_id} disconnected during message send")
            await self.disconnect(client_id)
            return False
            
        except Exception as e:
            logger.error(f"Failed to send message to client {client_id}: {str(e)}")
            # Remove potentially broken connection
            await self.disconnect(client_id)
            return False
    
    async def send_to_all(self, message: dict) -> int:
        """
        Send a message to all connected clients.
        
        Args:
            message: Dictionary containing the message data
            
        Returns:
            int: Number of clients that successfully received the message
        """
        if not isinstance(message, dict):
            logger.error(f"Message must be a dictionary, got {type(message)}")
            return 0
        
        # Add timestamp if not present
        if 'timestamp' not in message:
            import time
            message['timestamp'] = time.time()
        
        success_count = 0
        failed_clients = []
        
        # Get a snapshot of current connections
        with self._lock:
            client_ids = list(self.active_connections.keys())
        
        # Send to each client
        for client_id in client_ids:
            if await self.send_progress(client_id, message):
                success_count += 1
            else:
                failed_clients.append(client_id)
        
        if failed_clients:
            logger.warning(f"Failed to send message to clients: {failed_clients}")
        
        logger.debug(f"Broadcast message sent to {success_count}/{len(client_ids)} clients")
        return success_count
    
    def get_connection_count(self) -> int:
        """
        Get the number of active connections.
        
        Returns:
            int: Number of active WebSocket connections
        """
        with self._lock:
            return len(self.active_connections)
    
    def get_connected_clients(self) -> list:
        """
        Get a list of connected client IDs.
        
        Returns:
            list: List of client IDs currently connected
        """
        with self._lock:
            return list(self.active_connections.keys())
    
    async def cleanup_all_connections(self) -> None:
        """
        Close all active connections and clear the connection dictionary.
        Useful for application shutdown.
        """
        with self._lock:
            client_ids = list(self.active_connections.keys())
        
        logger.info(f"Cleaning up {len(client_ids)} active connections")
        
        # Disconnect all clients
        for client_id in client_ids:
            await self.disconnect(client_id)
        
        logger.info("All connections cleaned up")


# Global connection manager instance
connection_manager = ConnectionManager()


async def handle_websocket_disconnect(client_id: str) -> None:
    """
    Handle WebSocket disconnection cleanup.
    
    Args:
        client_id: ID of the client that disconnected
    """
    await connection_manager.disconnect(client_id)


def create_progress_message(
    status: str, 
    progress: Optional[float] = None, 
    message: Optional[str] = None, 
    data: Optional[dict] = None
) -> dict:
    """
    Create a standardized progress message format.
    
    Args:
        status: Status of the operation (e.g., 'processing', 'completed', 'error')
        progress: Progress percentage (0.0 to 100.0)
        message: Human-readable message
        data: Additional data payload
        
    Returns:
        dict: Formatted progress message
    """
    progress_msg = {
        'type': 'progress',
        'status': status
    }
    
    if progress is not None:
        progress_msg['progress'] = max(0.0, min(100.0, float(progress)))
    
    if message is not None:
        progress_msg['message'] = str(message)
    
    if data is not None:
        progress_msg['data'] = data
    
    return progress_msg


def create_error_message(error: str, error_code: Optional[str] = None) -> dict:
    """
    Create a standardized error message format.
    
    Args:
        error: Error message
        error_code: Optional error code
        
    Returns:
        dict: Formatted error message
    """
    error_msg = {
        'type': 'error',
        'status': 'error',
        'message': str(error)
    }
    
    if error_code:
        error_msg['error_code'] = str(error_code)
    
    return error_msg