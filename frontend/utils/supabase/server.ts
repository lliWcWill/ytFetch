import { createServerClient } from '@supabase/ssr'
import { cookies } from 'next/headers'

export async function createClient() {
  const cookieStore = await cookies()

  return createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      auth: {
        flowType: 'pkce',
        autoRefreshToken: true,
        persistSession: true,
        detectSessionInUrl: true,
      },
      cookies: {
        getAll() {
          return cookieStore.getAll()
        },
        setAll(cookiesToSet) {
          try {
            cookiesToSet.forEach(({ name, value, options }) => {
              // Determine if we're in production or using HTTPS
              const isProduction = process.env.NODE_ENV === 'production'
              const isSecure = process.env.NEXT_PUBLIC_API_URL?.startsWith('https://') || isProduction
              
              const cookieOptions = {
                ...options,
                path: '/',
                sameSite: 'lax' as const,
                secure: false, // Explicitly set to false for development HTTP
                httpOnly: false, // Must be false for client-side access
                maxAge: 60 * 60 * 24 * 7, // 7 days
              }
              
              // Only enable secure in production or HTTPS environments
              if (isSecure) {
                cookieOptions.secure = true
              }
              
              cookieStore.set(name, value, cookieOptions)
            })
          } catch (error) {
            // The `setAll` method was called from a Server Component.
            // This can be ignored if you have middleware refreshing
            // user sessions.
          }
        }
      }
    }
  )
}