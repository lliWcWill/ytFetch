import { supabase } from '@/providers/AuthProvider'

/**
 * Gets or creates a guest session ID for unauthenticated users
 */
export function getGuestSessionId(): string {
  const GUEST_SESSION_KEY = 'ytfetch-guest-session'
  
  // Check if we already have a guest session ID
  let sessionId = localStorage.getItem(GUEST_SESSION_KEY)
  
  if (!sessionId) {
    // Generate a new session ID
    sessionId = crypto.randomUUID ? crypto.randomUUID() : 
      'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
        const r = Math.random() * 16 | 0
        const v = c === 'x' ? r : (r & 0x3 | 0x8)
        return v.toString(16)
      })
    
    // Store it for future use
    localStorage.setItem(GUEST_SESSION_KEY, sessionId)
  }
  
  return sessionId
}

/**
 * Gets the current auth token from Supabase session
 * This is more reliable than parsing localStorage directly
 */
export async function getAuthToken(): Promise<string | null> {
  try {
    const { data: { session }, error } = await supabase.auth.getSession()
    
    if (error) {
      console.warn('Failed to get session:', error.message)
      return null
    }
    
    return session?.access_token || null
  } catch (error) {
    console.warn('Error getting auth token:', error)
    return null
  }
}

/**
 * Creates authenticated headers for API requests
 */
export async function createAuthHeaders(includeContentType = true): Promise<Record<string, string>> {
  const headers: Record<string, string> = {
    'Accept': 'application/json',
  }
  
  if (includeContentType) {
    headers['Content-Type'] = 'application/json'
  }
  
  // Add authorization header if user is authenticated
  const token = await getAuthToken()
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  } else {
    // For guest users, add the guest session ID
    headers['X-Guest-Session-ID'] = getGuestSessionId()
  }
  
  return headers
}

/**
 * Handles authentication errors and redirects
 */
export function handleAuthError() {
  if (typeof window !== 'undefined') {
    // Store current path for redirect after login
    sessionStorage.setItem('auth-redirect-to', window.location.pathname)
    window.location.href = '/login'
  }
}