'use client'

import { useEffect, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useAuth } from '@/providers/AuthProvider'
import { AlertCircle, Loader2 } from 'lucide-react'

export default function LoginPage() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const { user, signInWithGoogle, loading: authLoading, error, clearError } = useAuth()
  const [isSigningIn, setIsSigningIn] = useState(false)
  const [localError, setLocalError] = useState<string | null>(null)

  // Check for error in URL params (from OAuth callback)
  useEffect(() => {
    const errorParam = searchParams.get('error')
    const errorDescription = searchParams.get('error_description')
    
    if (errorParam) {
      const errorMessage = errorDescription 
        ? decodeURIComponent(errorDescription)
        : 'Authentication failed'
      setLocalError(`OAuth Error: ${errorMessage}`)
    }
  }, [searchParams])

  // Redirect if already authenticated
  useEffect(() => {
    if (!authLoading && user) {
      const redirectTo = sessionStorage.getItem('auth-redirect-to') || '/'
      sessionStorage.removeItem('auth-redirect-to')
      router.replace(redirectTo)
    }
  }, [user, authLoading, router])

  // Handle Google sign in
  const handleGoogleSignIn = async () => {
    if (isSigningIn) return
    
    setIsSigningIn(true)
    setLocalError(null)
    clearError()

    try {
      const { error: signInError } = await signInWithGoogle()
      
      if (signInError) {
        setLocalError(`Sign in failed: ${signInError.message || 'Unknown error'}`)
      }
      // Success case is handled by the auth state change listener
    } catch (error) {
      setLocalError(`Unexpected error: ${error instanceof Error ? error.message : 'Unknown error'}`)
    } finally {
      setIsSigningIn(false)
    }
  }

  // Show loading spinner while checking auth state
  if (authLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="flex flex-col items-center space-y-4">
          <Loader2 className="h-8 w-8 animate-spin text-orange-500" />
          <p className="text-sm text-muted-foreground">Checking authentication...</p>
        </div>
      </div>
    )
  }

  // Don't render if user is already authenticated
  if (user) {
    return null
  }

  const displayError = localError || error

  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-4">
      <div className="w-full max-w-md space-y-8">
        {/* Header */}
        <div className="text-center">
          <div className="mx-auto w-16 h-16 bg-gradient-to-r from-orange-500 to-red-500 rounded-xl flex items-center justify-center mb-6">
            <span className="text-2xl font-bold text-white">yt</span>
          </div>
          <h1 className="text-3xl font-bold tracking-tight">Welcome to ytFetch</h1>
          <p className="text-muted-foreground mt-2">
            Sign in to access powerful YouTube transcription tools
          </p>
        </div>

        {/* Login Card */}
        <Card className="border-muted">
          <CardHeader className="space-y-1 pb-6">
            <CardTitle className="text-2xl text-center">Sign in</CardTitle>
            <CardDescription className="text-center">
              Choose your preferred sign-in method
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Error Display */}
            {displayError && (
              <div className="flex items-center space-x-2 p-3 bg-destructive/10 border border-destructive/20 rounded-md text-destructive text-sm">
                <AlertCircle className="h-4 w-4 flex-shrink-0" />
                <span className="flex-1">{displayError}</span>
              </div>
            )}

            {/* Google Sign In Button */}
            <Button
              onClick={handleGoogleSignIn}
              disabled={isSigningIn}
              size="lg"
              className="w-full bg-white hover:bg-gray-50 text-gray-900 border border-gray-300 shadow-sm"
              variant="outline"
            >
              {isSigningIn ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <svg className="mr-2 h-4 w-4" viewBox="0 0 24 24">
                  <path
                    fill="currentColor"
                    d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                  />
                  <path
                    fill="currentColor"
                    d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                  />
                  <path
                    fill="currentColor"
                    d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                  />
                  <path
                    fill="currentColor"
                    d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                  />
                </svg>
              )}
              {isSigningIn ? 'Signing in...' : 'Continue with Google'}
            </Button>

            {/* Divider */}
            <div className="relative">
              <div className="absolute inset-0 flex items-center">
                <span className="w-full border-t border-muted" />
              </div>
              <div className="relative flex justify-center text-xs uppercase">
                <span className="bg-background px-2 text-muted-foreground">Features</span>
              </div>
            </div>

            {/* Features List */}
            <div className="space-y-3 text-sm text-muted-foreground">
              <div className="flex items-center space-x-2">
                <div className="w-2 h-2 bg-orange-500 rounded-full"></div>
                <span>AI-powered transcription with Groq</span>
              </div>
              <div className="flex items-center space-x-2">
                <div className="w-2 h-2 bg-orange-500 rounded-full"></div>
                <span>Multiple output formats (TXT, SRT, VTT)</span>
              </div>
              <div className="flex items-center space-x-2">
                <div className="w-2 h-2 bg-orange-500 rounded-full"></div>
                <span>Bulk playlist processing</span>
              </div>
              <div className="flex items-center space-x-2">
                <div className="w-2 h-2 bg-orange-500 rounded-full"></div>
                <span>Real-time progress tracking</span>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Footer */}
        <div className="text-center text-xs text-muted-foreground">
          <p>
            By signing in, you agree to our{' '}
            <a href="/terms" className="underline hover:text-foreground">Terms of Service</a>
            {' '}and{' '}
            <a href="/privacy" className="underline hover:text-foreground">Privacy Policy</a>
          </p>
        </div>
      </div>
    </div>
  )
}