import { createServerClient } from '@supabase/ssr'
import { NextResponse, type NextRequest } from 'next/server'

export async function updateSession(request: NextRequest) {
  let supabaseResponse = NextResponse.next({
    request
  })

  const supabase = createServerClient(
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
          return request.cookies.getAll()
        },
        setAll(cookiesToSet) {
          cookiesToSet.forEach(({ name, value, options }) => request.cookies.set(name, value))
          supabaseResponse = NextResponse.next({
            request
          })
          
          // Determine if we're in production or using HTTPS
          const isProduction = process.env.NODE_ENV === 'production'
          const url = request.url
          const isSecure = url.startsWith('https://') || isProduction
          
          cookiesToSet.forEach(({ name, value, options }) => {
            const cookieOptions = {
              name,
              value,
              ...options,
              path: '/',
              sameSite: 'lax' as const,
              secure: false, // Explicitly set to false for development
              httpOnly: false, // Must be false for client-side access
              maxAge: options?.maxAge || 60 * 60 * 24 * 7, // 7 days
            }
            
            // Only enable secure in production or HTTPS environments
            if (isSecure) {
              cookieOptions.secure = true
            }
            
            supabaseResponse.cookies.set(cookieOptions)
          })
        }
      }
    }
  )

  // IMPORTANT: Avoid writing any logic between createServerClient and
  // supabase.auth.getUser(). A simple mistake could make it very hard to debug.
  await supabase.auth.getUser()

  return supabaseResponse
}