import { createBrowserClient } from '@supabase/ssr'
import { getSupabaseURL, getSupabaseAnonKey } from './config'

export function createClient() {
  // Determine if we're in a secure context
  const isSecureContext = typeof window !== 'undefined' && window.location.protocol === 'https:'
  
  return createBrowserClient(
    getSupabaseURL(),
    getSupabaseAnonKey(),
    {
      auth: {
        flowType: 'pkce',
        autoRefreshToken: true,
        persistSession: true,
        detectSessionInUrl: true,
      },
      cookies: {
        // Use default cookie handling from @supabase/ssr with proper options
        get(name: string) {
          if (typeof window === 'undefined') return null
          const cookies = document.cookie.split('; ')
          const cookie = cookies.find(c => c.startsWith(`${name}=`))
          const value = cookie ? decodeURIComponent(cookie.split('=')[1]) : null
          console.log(`[Cookie Get] ${name}:`, value ? 'found' : 'not found', 'All cookies:', document.cookie)
          return value
        },
        set(name: string, value: string, options?: any) {
          if (typeof window === 'undefined') return
          
          const cookieOptions = {
            path: '/',
            maxAge: 60 * 60 * 24 * 7, // 7 days
            sameSite: 'lax' as const,
            secure: false, // Explicitly set to false for development
            ...options
          }
          
          let cookieString = `${name}=${encodeURIComponent(value)}`
          cookieString += `; path=${cookieOptions.path}`
          cookieString += `; max-age=${cookieOptions.maxAge}`
          cookieString += `; samesite=${cookieOptions.sameSite}`
          
          // Only add secure flag if in HTTPS context
          if (cookieOptions.secure && isSecureContext) {
            cookieString += '; secure'
          }
          
          document.cookie = cookieString
          console.log(`[Cookie Set] ${name}:`, cookieString)
        },
        remove(name: string, options?: any) {
          if (typeof window === 'undefined') return
          
          const cookieOptions = {
            path: '/',
            ...options
          }
          
          document.cookie = `${name}=; path=${cookieOptions.path}; expires=Thu, 01 Jan 1970 00:00:00 GMT`
        }
      }
    }
  )
}