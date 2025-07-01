import { NextResponse } from 'next/server'
import { createClient } from '@/utils/supabase/server'

export async function GET(request: Request) {
  const { searchParams, origin } = new URL(request.url)
  const code = searchParams.get('code')
  const error = searchParams.get('error')
  const errorDescription = searchParams.get('error_description')
  const errorCode = searchParams.get('error_code')
  
  // Log all received parameters for debugging
  console.log('Auth callback params:', {
    code: code ? 'present' : 'missing',
    error,
    errorDescription,
    errorCode,
    searchParams: Object.fromEntries(searchParams.entries())
  })
  
  // Check for OAuth errors from the provider
  if (error) {
    console.error('OAuth error:', { error, errorDescription, errorCode })
    
    // Handle specific OAuth state errors
    if (error === 'invalid_request' && errorCode === 'bad_oauth_state') {
      console.error('OAuth state mismatch detected - this indicates PKCE/state parameter issues')
      return NextResponse.redirect(`${origin}/auth/auth-code-error?error=state_mismatch&description=OAuth+state+parameter+mismatch`)
    }
    
    return NextResponse.redirect(`${origin}/auth/auth-code-error?error=${error}`)
  }
  
  if (code) {
    try {
      const supabase = await createClient()
      
      // Log the code exchange attempt
      console.log('Attempting to exchange code for session...')
      
      const { data, error: exchangeError } = await supabase.auth.exchangeCodeForSession(code)
      
      if (!exchangeError && data?.session) {
        console.log('Successfully exchanged code for session')
        
        // Successfully authenticated - check for stored redirect
        const next = searchParams.get('next') || searchParams.get('redirect_to')
        
        // Validate redirect URL to prevent open redirects
        let redirectUrl = `${origin}/`
        if (next && next.startsWith('/')) {
          redirectUrl = `${origin}${next}`
        }
        
        // For debugging
        console.log('Auth callback redirect:', { next, redirectUrl })
        
        // Add a refresh parameter to force page reload
        const finalUrl = new URL(redirectUrl)
        finalUrl.searchParams.set('auth_success', '1')
        
        return NextResponse.redirect(finalUrl.toString())
      } else {
        console.error('Code exchange error:', exchangeError)
        return NextResponse.redirect(`${origin}/auth/auth-code-error?error=exchange_failed&details=${encodeURIComponent(exchangeError?.message || 'Unknown error')}`)
      }
    } catch (err) {
      console.error('Unexpected error during auth:', err)
      return NextResponse.redirect(`${origin}/auth/auth-code-error?error=unexpected&details=${encodeURIComponent(err instanceof Error ? err.message : 'Unknown error')}`)
    }
  }

  // No code provided
  console.error('No auth code provided in callback')
  return NextResponse.redirect(`${origin}/auth/auth-code-error?error=no_code`)
}