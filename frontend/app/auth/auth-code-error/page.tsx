'use client'

import { Button } from '@/components/ui/button'
import { useRouter, useSearchParams } from 'next/navigation'
import { AlertCircle } from 'lucide-react'
import { Suspense } from 'react'

function AuthErrorContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  
  const error = searchParams.get('error')
  const description = searchParams.get('description')
  const details = searchParams.get('details')

  const getErrorInfo = () => {
    switch (error) {
      case 'state_mismatch':
        return {
          title: 'OAuth State Error',
          message: 'There was a problem with the authentication state. This can happen if cookies are disabled or if there was a network issue during sign-in.',
          suggestion: 'Please try signing in again and make sure cookies are enabled in your browser.'
        }
      case 'exchange_failed':
        return {
          title: 'Authentication Failed',
          message: 'Failed to complete the sign-in process.',
          suggestion: 'Please try signing in again. If the problem persists, check your internet connection.'
        }
      case 'unexpected':
        return {
          title: 'Unexpected Error',
          message: 'An unexpected error occurred during authentication.',
          suggestion: 'Please try again. If the problem continues, contact support.'
        }
      case 'no_code':
        return {
          title: 'Authentication Incomplete',
          message: 'The authentication process was not completed properly.',
          suggestion: 'Please try signing in again.'
        }
      default:
        return {
          title: 'Authentication Error',
          message: description || 'There was an error during the authentication process. This could be due to an expired link or a configuration issue.',
          suggestion: 'Please try signing in again.'
        }
    }
  }

  const errorInfo = getErrorInfo()

  const handleRetry = () => {
    // Clear any stored auth state that might be causing issues
    if (typeof window !== 'undefined') {
      sessionStorage.removeItem('auth-redirect-to')
      localStorage.removeItem('supabase.auth.token')
      // Clear any Supabase auth cookies
      document.cookie.split(";").forEach((c) => {
        if (c.includes('sb-')) {
          const eqPos = c.indexOf("=")
          const name = eqPos > -1 ? c.substr(0, eqPos) : c
          document.cookie = name + "=;expires=Thu, 01 Jan 1970 00:00:00 GMT;path=/;domain=" + window.location.hostname
        }
      })
    }
    router.push('/')
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-4">
      <div className="max-w-md w-full space-y-6 text-center">
        <div className="mx-auto w-16 h-16 bg-destructive/10 rounded-full flex items-center justify-center">
          <AlertCircle className="h-8 w-8 text-destructive" />
        </div>
        
        <div className="space-y-2">
          <h1 className="text-2xl font-semibold">{errorInfo.title}</h1>
          <p className="text-muted-foreground">
            {errorInfo.message}
          </p>
          <p className="text-sm text-muted-foreground">
            {errorInfo.suggestion}
          </p>
        </div>

        {details && (
          <details className="text-left bg-muted/50 p-3 rounded-lg">
            <summary className="cursor-pointer text-sm font-medium">
              Technical Details
            </summary>
            <pre className="mt-2 text-xs bg-muted p-2 rounded overflow-auto whitespace-pre-wrap">
              {details}
            </pre>
          </details>
        )}

        <div className="space-y-3">
          <Button 
            onClick={handleRetry}
            size="lg"
            className="w-full"
          >
            Try Again
          </Button>
          
          <Button 
            onClick={() => router.push('/')}
            variant="outline"
            size="lg"
            className="w-full"
          >
            Go to Home
          </Button>
        </div>

        <p className="text-xs text-muted-foreground">
          If this error persists, please contact support.
        </p>
      </div>
    </div>
  )
}

export default function AuthCodeErrorPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-orange-500"></div>
      </div>
    }>
      <AuthErrorContent />
    </Suspense>
  )
}