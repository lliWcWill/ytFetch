'use client'

import { createContext, useContext, useEffect, useState, useCallback, ReactNode, use } from 'react'
import { createClient, type AuthChangeEvent, type Session, type User } from '@supabase/supabase-js'
import { useRouter } from 'next/navigation'
import type { Database } from '@/types/supabase'

// Environment variables validation
const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY

if (!supabaseUrl || !supabaseAnonKey) {
  throw new Error('Missing Supabase environment variables')
}

// Create Supabase client with modern configuration
const supabase = createClient<Database>(supabaseUrl, supabaseAnonKey, {
  auth: {
    autoRefreshToken: true,
    persistSession: true,
    detectSessionInUrl: true,
    flowType: 'pkce',
    storage: {
      getItem: (key: string) => {
        if (typeof window !== 'undefined') {
          return window.localStorage.getItem(key)
        }
        return null
      },
      setItem: (key: string, value: string) => {
        if (typeof window !== 'undefined') {
          window.localStorage.setItem(key, value)
        }
      },
      removeItem: (key: string) => {
        if (typeof window !== 'undefined') {
          window.localStorage.removeItem(key)
        }
      }
    }
  },
  global: {
    headers: {
      'X-Client-Info': 'ytfetch-frontend-auth'
    }
  }
})

// Types
interface AuthContextType {
  user: User | null
  session: Session | null
  loading: boolean
  error: string | null
  signInWithGoogle: () => Promise<{ error?: any }>
  signOut: () => Promise<void>
  clearError: () => void
  refreshSession: () => Promise<void>
}

interface AuthProviderProps {
  children: ReactNode
}

interface AuthStateType {
  user: User | null
  session: Session | null
  loading: boolean
  error: string | null
}

// Create context
const AuthContext = createContext<AuthContextType | undefined>(undefined)

// Custom hook to use auth context
export function useAuth(): AuthContextType {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}

// Auth provider component
export function AuthProvider({ children }: AuthProviderProps) {
  const router = useRouter()
  
  // State management with proper typing
  const [authState, setAuthState] = useState<AuthStateType>({
    user: null,
    session: null,
    loading: true,
    error: null
  })

  // Clear error function
  const clearError = useCallback(() => {
    setAuthState(prev => ({ ...prev, error: null }))
  }, [])

  // Handle auth state changes
  const handleAuthChange = useCallback((event: AuthChangeEvent, session: Session | null) => {
    console.log('Auth event:', event, session?.user?.email)
    
    setAuthState(prev => ({
      ...prev,
      user: session?.user ?? null,
      session,
      loading: false,
      error: null
    }))

    // Handle redirects based on auth events
    switch (event) {
      case 'SIGNED_IN':
        // Redirect to home or intended destination
        const redirectTo = sessionStorage.getItem('auth-redirect-to') || '/'
        sessionStorage.removeItem('auth-redirect-to')
        router.push(redirectTo)
        break
      case 'SIGNED_OUT':
        // Clear any cached data and redirect to login
        router.push('/login')
        break
      case 'TOKEN_REFRESHED':
        console.log('Token refreshed successfully')
        break
      case 'USER_UPDATED':
        console.log('User profile updated')
        break
    }
  }, [router])

  // Initialize auth state and set up listener
  useEffect(() => {
    let mounted = true

    // Get initial session
    const initializeAuth = async () => {
      try {
        const { data: { session }, error } = await supabase.auth.getSession()
        
        if (error) {
          console.error('Error getting session:', error.message)
          if (mounted) {
            setAuthState(prev => ({
              ...prev,
              error: `Session error: ${error.message}`,
              loading: false
            }))
          }
          return
        }

        if (mounted) {
          setAuthState({
            user: session?.user ?? null,
            session,
            loading: false,
            error: null
          })
        }
      } catch (error) {
        console.error('Auth initialization error:', error)
        if (mounted) {
          setAuthState(prev => ({
            ...prev,
            error: 'Failed to initialize authentication',
            loading: false
          }))
        }
      }
    }

    initializeAuth()

    // Set up auth state listener
    const { data: { subscription } } = supabase.auth.onAuthStateChange(handleAuthChange)

    return () => {
      mounted = false
      subscription.unsubscribe()
    }
  }, [handleAuthChange])

  // Sign in with Google
  const signInWithGoogle = useCallback(async () => {
    clearError()
    
    try {
      const { error } = await supabase.auth.signInWithOAuth({
        provider: 'google',
        options: {
          redirectTo: `${window.location.origin}/auth/callback`,
          queryParams: {
            access_type: 'offline',
            prompt: 'consent',
          }
        }
      })

      if (error) {
        const errorMessage = `Google sign-in failed: ${error.message}`
        setAuthState(prev => ({ ...prev, error: errorMessage }))
        return { error }
      }

      return {}
    } catch (error) {
      const errorMessage = `Sign-in error: ${error instanceof Error ? error.message : 'Unknown error'}`
      setAuthState(prev => ({ ...prev, error: errorMessage }))
      return { error }
    }
  }, [clearError])

  // Sign out
  const signOut = useCallback(async () => {
    clearError()
    
    try {
      const { error } = await supabase.auth.signOut()
      
      if (error) {
        console.error('Sign out error:', error.message)
        setAuthState(prev => ({ ...prev, error: `Sign out failed: ${error.message}` }))
        return
      }

      // Clear local state immediately
      setAuthState({
        user: null,
        session: null,
        loading: false,
        error: null
      })

      // Clear any cached data
      if (typeof window !== 'undefined') {
        localStorage.removeItem('supabase.auth.token')
        sessionStorage.clear()
      }

    } catch (error) {
      const errorMessage = `Sign out error: ${error instanceof Error ? error.message : 'Unknown error'}`
      setAuthState(prev => ({ ...prev, error: errorMessage }))
    }
  }, [clearError])

  // Refresh session
  const refreshSession = useCallback(async () => {
    try {
      const { data: { session }, error } = await supabase.auth.refreshSession()
      
      if (error) {
        console.error('Session refresh error:', error.message)
        setAuthState(prev => ({ ...prev, error: `Session refresh failed: ${error.message}` }))
        return
      }

      if (session) {
        setAuthState(prev => ({
          ...prev,
          user: session.user,
          session,
          error: null
        }))
      }
    } catch (error) {
      const errorMessage = `Session refresh error: ${error instanceof Error ? error.message : 'Unknown error'}`
      setAuthState(prev => ({ ...prev, error: errorMessage }))
    }
  }, [])

  // Context value
  const value: AuthContextType = {
    user: authState.user,
    session: authState.session,
    loading: authState.loading,
    error: authState.error,
    signInWithGoogle,
    signOut,
    clearError,
    refreshSession
  }

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  )
}

// Higher-order component for protected routes
export function withAuth<T extends {}>(Component: React.ComponentType<T>) {
  return function AuthenticatedComponent(props: T) {
    const { user, loading } = useAuth()
    const router = useRouter()

    useEffect(() => {
      if (!loading && !user) {
        // Store the current path for redirect after login
        sessionStorage.setItem('auth-redirect-to', window.location.pathname)
        router.push('/login')
      }
    }, [user, loading, router])

    if (loading) {
      return (
        <div className="min-h-screen flex items-center justify-center">
          <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-orange-500"></div>
        </div>
      )
    }

    if (!user) {
      return null // Will redirect to login
    }

    return <Component {...props} />
  }
}

// Component for handling authentication loading states
export function AuthLoadingBoundary({ children }: { children: ReactNode }) {
  const { loading } = useAuth()

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="flex flex-col items-center space-y-4">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-orange-500"></div>
          <p className="text-sm text-muted-foreground">Loading...</p>
        </div>
      </div>
    )
  }

  return <>{children}</>
}

export { supabase }