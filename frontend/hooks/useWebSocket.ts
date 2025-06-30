import { useEffect, useRef, useState } from 'react'

export interface WebSocketMessage {
  type: string
  status: string
  progress?: number
  message?: string
  data?: any
  error_code?: string
  details?: any
  timestamp?: number
}

export interface UseWebSocketReturn {
  readyState: number
  lastMessage: WebSocketMessage | null
  sendMessage: (message: any) => void
}

export function useWebSocket(
  url: string | null,
  onMessage?: (message: WebSocketMessage) => void
): UseWebSocketReturn {
  const [readyState, setReadyState] = useState<number>(WebSocket.CONNECTING)
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null)
  const websocketRef = useRef<WebSocket | null>(null)
  const pingIntervalRef = useRef<NodeJS.Timeout | null>(null)
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const onMessageRef = useRef(onMessage)

  // Update the ref when onMessage changes
  useEffect(() => {
    onMessageRef.current = onMessage
  }, [onMessage])

  const sendMessage = (message: any) => {
    if (websocketRef.current && websocketRef.current.readyState === WebSocket.OPEN) {
      websocketRef.current.send(JSON.stringify(message))
    }
  }

  useEffect(() => {
    // Clear any pending reconnect timeout
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }

    if (!url) {
      // Clean up existing connection
      if (websocketRef.current) {
        const ws = websocketRef.current
        websocketRef.current = null
        
        if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
          ws.close()
        }
      }
      if (pingIntervalRef.current) {
        clearInterval(pingIntervalRef.current)
        pingIntervalRef.current = null
      }
      setReadyState(WebSocket.CLOSED)
      return
    }

    // Prevent creating a new connection if one already exists for this URL
    if (websocketRef.current && websocketRef.current.url === url && 
        (websocketRef.current.readyState === WebSocket.OPEN || 
         websocketRef.current.readyState === WebSocket.CONNECTING)) {
      console.log('WebSocket already connected or connecting to:', url)
      return
    }

    console.log('Creating new WebSocket connection to:', url)
    const ws = new WebSocket(url)
    websocketRef.current = ws

    ws.onopen = () => {
      console.log('WebSocket connected:', url)
      setReadyState(WebSocket.OPEN)
      
      // Send a ping message every 30 seconds to keep the connection alive
      pingIntervalRef.current = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'ping' }))
        }
      }, 30000)
    }

    ws.onmessage = (event) => {
      try {
        const message: WebSocketMessage = JSON.parse(event.data)
        console.log('WebSocket message parsed:', message)
        setLastMessage(message)
        // Use the ref to call the latest onMessage callback
        if (onMessageRef.current) {
          onMessageRef.current(message)
        }
      } catch (error) {
        console.error('Failed to parse WebSocket message:', error)
      }
    }

    ws.onclose = (event) => {
      console.log('WebSocket closed:', event.code, event.reason)
      setReadyState(WebSocket.CLOSED)
      if (pingIntervalRef.current) {
        clearInterval(pingIntervalRef.current)
        pingIntervalRef.current = null
      }
    }

    ws.onerror = (error) => {
      console.error('WebSocket error:', error)
      setReadyState(WebSocket.CLOSED)
    }

    return () => {
      console.log('Cleaning up WebSocket connection:', url)
      if (pingIntervalRef.current) {
        clearInterval(pingIntervalRef.current)
        pingIntervalRef.current = null
      }
      // Only close if this is still our current WebSocket
      if (websocketRef.current === ws) {
        websocketRef.current = null
        if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
          ws.close()
        }
      }
    }
  }, [url]) // Remove onMessage from dependencies since we use a ref

  return {
    readyState,
    lastMessage,
    sendMessage
  }
}