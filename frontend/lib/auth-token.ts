import { supabase } from '@/providers/AuthProvider'

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