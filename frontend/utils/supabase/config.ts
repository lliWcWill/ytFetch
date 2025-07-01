// Supabase configuration helpers for handling different environments

export function getSupabaseURL() {
  return process.env.NEXT_PUBLIC_SUPABASE_URL!
}

export function getSupabaseAnonKey() {
  return process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
}

export function getAuthCallbackURL() {
  // In development, use the actual URL being accessed
  if (typeof window !== 'undefined') {
    return `${window.location.origin}/auth/callback`
  }
  
  // For server-side rendering
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:3000'
  const url = new URL(apiUrl)
  
  // Use port 3000 for Next.js frontend
  const frontendPort = '3000'
  
  return `${url.protocol}//${url.hostname}:${frontendPort}/auth/callback`
}

export function getCookieOptions(isProduction: boolean = process.env.NODE_ENV === 'production') {
  // Check if we're using HTTPS
  const isSecure = (typeof window !== 'undefined' && window.location.protocol === 'https:') || 
                   process.env.NEXT_PUBLIC_API_URL?.startsWith('https://') || 
                   isProduction
  
  return {
    domain: undefined, // Let the browser handle domain automatically
    path: '/',
    secure: false, // Explicitly set to false for development to support HTTP
    sameSite: 'lax' as const,
    maxAge: 60 * 60 * 24 * 7, // 7 days
    httpOnly: false, // Must be false for browser cookies
  }
}