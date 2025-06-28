'use client'

import { useEffect, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { createClient } from '@supabase/supabase-js'
import { Loader2, AlertCircle, CheckCircle } from 'lucide-react'

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!

const supabase = createClient(supabaseUrl, supabaseAnonKey)

export default function AuthCallbackPage() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading')
  const [message, setMessage] = useState('')

  useEffect(() => {
    const handleAuthCallback = async () => {
      try {
        // Get the code and state from URL parameters
        const code = searchParams.get('code')
        const error = searchParams.get('error')
        const errorDescription = searchParams.get('error_description')

        // Handle OAuth errors
        if (error) {
          setStatus('error')
          setMessage(errorDescription || 'Authentication failed')
          
          // Redirect to login with error after a delay
          setTimeout(() => {
            router.push(`/login?error=${error}&error_description=${encodeURIComponent(errorDescription || 'Authentication failed')}`)
          }, 3000)
          return
        }

        // Exchange the code for a session
        if (code) {
          const { data, error: exchangeError } = await supabase.auth.exchangeCodeForSession(code)

          if (exchangeError) {
            console.error('Code exchange error:', exchangeError)
            setStatus('error')
            setMessage(`Session creation failed: ${exchangeError.message}`)
            
            setTimeout(() => {
              router.push('/login?error=session_failed')
            }, 3000)
            return
          }

          if (data.session) {
            setStatus('success')
            setMessage('Successfully signed in! Redirecting...')
            
            // Get redirect destination
            const redirectTo = sessionStorage.getItem('auth-redirect-to') || '/'
            sessionStorage.removeItem('auth-redirect-to')
            
            // Small delay to show success message
            setTimeout(() => {
              router.push(redirectTo)
            }, 1500)
            return
          }
        }

        // Fallback: try to get existing session
        const { data: { session }, error: sessionError } = await supabase.auth.getSession()

        if (sessionError) {
          console.error('Session check error:', sessionError)
          setStatus('error')
          setMessage(`Session validation failed: ${sessionError.message}`)
          
          setTimeout(() => {
            router.push('/login?error=session_validation_failed')
          }, 3000)
          return
        }

        if (session) {
          setStatus('success')
          setMessage('Authentication successful! Redirecting...')
          
          const redirectTo = sessionStorage.getItem('auth-redirect-to') || '/'
          sessionStorage.removeItem('auth-redirect-to')
          
          setTimeout(() => {
            router.push(redirectTo)
          }, 1500)
        } else {
          setStatus('error')
          setMessage('No valid session found')
          
          setTimeout(() => {
            router.push('/login?error=no_session')
          }, 3000)
        }

      } catch (error) {
        console.error('Auth callback error:', error)
        setStatus('error')
        setMessage(`Unexpected error: ${error instanceof Error ? error.message : 'Unknown error'}`)
        
        setTimeout(() => {
          router.push('/login?error=callback_failed')
        }, 3000)
      }
    }

    handleAuthCallback()
  }, [searchParams, router])

  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <div className="text-center space-y-6 p-8">
        {/* Logo */}
        <div className="mx-auto w-16 h-16 bg-gradient-to-r from-orange-500 to-red-500 rounded-xl flex items-center justify-center">
          <span className="text-2xl font-bold text-white">yt</span>
        </div>

        {/* Status Display */}
        {status === 'loading' && (
          <>
            <Loader2 className="mx-auto h-8 w-8 animate-spin text-orange-500" />
            <div className="space-y-2">
              <h1 className="text-2xl font-semibold">Completing sign in...</h1>
              <p className="text-muted-foreground">Please wait while we verify your authentication</p>
            </div>
          </>
        )}

        {status === 'success' && (
          <>
            <CheckCircle className="mx-auto h-8 w-8 text-green-500" />
            <div className="space-y-2">
              <h1 className="text-2xl font-semibold text-green-600">Success!</h1>
              <p className="text-muted-foreground">{message}</p>
            </div>
          </>
        )}

        {status === 'error' && (
          <>
            <AlertCircle className="mx-auto h-8 w-8 text-red-500" />
            <div className="space-y-2">
              <h1 className="text-2xl font-semibold text-red-600">Authentication Failed</h1>
              <p className="text-muted-foreground">{message}</p>
              <p className="text-sm text-muted-foreground">You will be redirected to the login page shortly...</p>
            </div>
          </>
        )}

        {/* Loading indicator for all states */}
        <div className="flex justify-center space-x-1">
          <div className="w-2 h-2 bg-orange-500 rounded-full animate-pulse"></div>
          <div className="w-2 h-2 bg-orange-500 rounded-full animate-pulse delay-75"></div>
          <div className="w-2 h-2 bg-orange-500 rounded-full animate-pulse delay-150"></div>
        </div>
      </div>
    </div>
  )
}