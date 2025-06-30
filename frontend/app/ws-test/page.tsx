'use client'

import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

export default function WebSocketTestPage() {
  const [ws, setWs] = useState<WebSocket | null>(null)
  const [messages, setMessages] = useState<string[]>([])
  const [status, setStatus] = useState<string>('Disconnected')
  const [testId, setTestId] = useState<string>('test_' + Date.now())

  const connect = () => {
    const url = `ws://localhost:8000/ws/${testId}`
    console.log('Connecting to:', url)
    
    const websocket = new WebSocket(url)
    
    websocket.onopen = () => {
      console.log('WebSocket opened')
      setStatus('Connected')
      setMessages(prev => [...prev, `Connected to ${url}`])
    }
    
    websocket.onmessage = (event) => {
      console.log('Message received:', event.data)
      setMessages(prev => [...prev, `Received: ${event.data}`])
    }
    
    websocket.onclose = (event) => {
      console.log('WebSocket closed:', event.code, event.reason)
      setStatus(`Closed (${event.code}: ${event.reason || 'No reason'})`)
      setMessages(prev => [...prev, `Connection closed: ${event.code} - ${event.reason || 'No reason'}`])
      setWs(null)
    }
    
    websocket.onerror = (error) => {
      console.error('WebSocket error:', error)
      setStatus('Error')
      setMessages(prev => [...prev, `Error: ${error}`])
    }
    
    setWs(websocket)
  }
  
  const disconnect = () => {
    if (ws) {
      ws.close()
      setWs(null)
    }
  }
  
  const sendPing = () => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      const message = JSON.stringify({ type: 'ping', timestamp: Date.now() })
      ws.send(message)
      setMessages(prev => [...prev, `Sent: ${message}`])
    }
  }
  
  const clearMessages = () => {
    setMessages([])
  }

  return (
    <div className="container mx-auto p-8">
      <Card>
        <CardHeader>
          <CardTitle>WebSocket Connection Test</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div>
              <p className="text-sm text-muted-foreground">Test ID: {testId}</p>
              <p className="text-sm font-medium">Status: {status}</p>
            </div>
            
            <div className="flex gap-2">
              <Button onClick={connect} disabled={ws !== null}>
                Connect
              </Button>
              <Button onClick={disconnect} disabled={ws === null} variant="destructive">
                Disconnect
              </Button>
              <Button onClick={sendPing} disabled={ws === null || ws.readyState !== WebSocket.OPEN}>
                Send Ping
              </Button>
              <Button onClick={clearMessages} variant="outline">
                Clear Messages
              </Button>
            </div>
            
            <div className="border rounded p-4 h-64 overflow-y-auto bg-muted/50">
              <p className="text-sm font-medium mb-2">Messages:</p>
              {messages.length === 0 ? (
                <p className="text-sm text-muted-foreground">No messages yet...</p>
              ) : (
                messages.map((msg, idx) => (
                  <p key={idx} className="text-sm font-mono mb-1">
                    {msg}
                  </p>
                ))
              )}
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}