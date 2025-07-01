'use client'

import { createContext, useContext, useEffect, useState, useCallback, ReactNode } from 'react'
import { type AuthChangeEvent, type Session, type User } from '@supabase/supabase-js'
import { useRouter } from 'next/navigation'
import { createClient } from '@/utils/supabase/client'
import type { Database } from '@/types/supabase'

// Create Supabase client using the new SSR approach
const supabase = createClient()

// Types
interface UserProfile {
  id: string
  tier_id: string
  videos_processed_this_month: number
  jobs_created_this_month: number
  total_videos_processed: number
  total_jobs_created: number
  subscription_status: 'active' | 'cancelled' | 'suspended' | 'expired'
  subscription_expires_at: string | null
  created_at: string
  updated_at: string
  last_active_at: string
  tier?: UserTier
}

interface UserTier {
  id: string
  name: string
  display_name: string
  description: string | null
  max_videos_per_job: number
  max_jobs_per_month: number
  max_concurrent_jobs: number
  max_video_duration_minutes: number
  priority_processing: boolean
  webhook_support: boolean
  api_access: boolean
  price_monthly: number
  price_yearly: number
  is_active: boolean
}

interface AuthContextType {
  user: User | null
  session: Session | null
  profile: UserProfile | null
  loading: boolean
  error: string | null
  signInWithGoogle: () => Promise<{ error?: any }>
  signOut: () => Promise<void>
  clearError: () => void
  refreshSession: () => Promise<void>
  refreshProfile: () => Promise<void>
}

interface AuthProviderProps {
  children: ReactNode
}

interface AuthStateType {
  user: User | null
  session: Session | null
  profile: UserProfile | null
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
    profile: null,
    loading: true,
    error: null
  })

  // Clear error function
  const clearError = useCallback(() => {
    setAuthState(prev => ({ ...prev, error: null }))
  }, [])

  // Fetch user profile - currently we don't have a user_profiles table
  // This is a placeholder for future implementation
  const fetchUserProfile = useCallback(async (userId: string): Promise<UserProfile | null> => {
    // For now, return null as we don't have a user_profiles table
    // Token balance is fetched separately through the API
    return null
  }, [])

  // Handle auth state changes
  const handleAuthChange = useCallback(async (event: AuthChangeEvent, session: Session | null) => {
    console.log('Auth event:', event, session?.user?.email)
    
    // Fetch profile if user is signed in
    let profile: UserProfile | null = null
    if (session?.user) {
      profile = await fetchUserProfile(session.user.id)
    }
    
    setAuthState(prev => ({
      ...prev,
      user: session?.user ?? null,
      session,
      profile,
      loading: false,
      error: null
    }))

    // Log auth events but don't handle redirects here
    // Redirects should be handled by the auth callback route
    switch (event) {
      case 'SIGNED_IN':
        console.log('User signed in successfully')
        // Force a re-render of components that depend on auth state
        window.dispatchEvent(new Event('auth-state-changed'))
        break
      case 'SIGNED_OUT':
        console.log('User signed out - guest mode active')
        window.dispatchEvent(new Event('auth-state-changed'))
        break
      case 'TOKEN_REFRESHED':
        console.log('Token refreshed successfully')
        break
      case 'USER_UPDATED':
        console.log('User profile updated')
        break
    }
  }, [fetchUserProfile])

  // Initialize auth state and set up listener
  useEffect(() => {
    let mounted = true

    // Get initial session
    const initializeAuth = async () => {
      try {
        // Add a small delay to ensure Supabase client is fully initialized
        await new Promise(resolve => setTimeout(resolve, 100))
        
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
          // Fetch profile if user is authenticated
          let profile: UserProfile | null = null
          if (session?.user) {
            profile = await fetchUserProfile(session.user.id)
          }
          
          setAuthState({
            user: session?.user ?? null,
            session,
            profile,
            loading: false,
            error: null
          })
          
          // If we have a session, dispatch auth state changed event
          if (session?.user) {
            console.log('Initial session found, dispatching auth-state-changed')
            window.dispatchEvent(new Event('auth-state-changed'))
          }
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

    // Refresh auth state when window regains focus or becomes visible
    const handleVisibilityChange = () => {
      if (!document.hidden) {
        initializeAuth()
      }
    }

    const handleFocus = () => {
      initializeAuth()
    }


    document.addEventListener('visibilitychange', handleVisibilityChange)
    window.addEventListener('focus', handleFocus)

    return () => {
      mounted = false
      subscription.unsubscribe()
      document.removeEventListener('visibilitychange', handleVisibilityChange)
      window.removeEventListener('focus', handleFocus)
    }
  }, [handleAuthChange, fetchUserProfile, router])

  // Sign in with Google
  const signInWithGoogle = useCallback(async () => {
    clearError()
    
    try {
      // Clear any existing auth state that might interfere
      await supabase.auth.signOut({ scope: 'local' })
      
      // Small delay to ensure cleanup is complete
      await new Promise(resolve => setTimeout(resolve, 100))
      
      // Get the stored redirect path
      const storedRedirect = sessionStorage.getItem('auth-redirect-to')
      const redirectParam = storedRedirect ? `?next=${encodeURIComponent(storedRedirect)}` : ''
      
      const redirectUrl = `${window.location.origin}/auth/callback${redirectParam}`
      console.log('OAuth redirect URL:', redirectUrl)
      console.log('Current origin:', window.location.origin)
      
      const { error } = await supabase.auth.signInWithOAuth({
        provider: 'google',
        options: {
          redirectTo: redirectUrl,
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
        profile: null,
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
      // First check if we have a session to refresh
      const { data: { session: currentSession } } = await supabase.auth.getSession()
      
      if (!currentSession) {
        console.log('No session to refresh')
        return
      }
      
      const { data: { session }, error } = await supabase.auth.refreshSession()
      
      if (error) {
        console.error('Session refresh error:', error.message)
        setAuthState(prev => ({ ...prev, error: `Session refresh failed: ${error.message}` }))
        return
      }

      if (session) {
        // Fetch profile after session refresh
        const profile = await fetchUserProfile(session.user.id)
        
        setAuthState(prev => ({
          ...prev,
          user: session.user,
          session,
          profile,
          error: null
        }))
        
        // Dispatch auth state changed event after successful refresh
        console.log('Session refreshed, dispatching auth-state-changed')
        window.dispatchEvent(new Event('auth-state-changed'))
      }
    } catch (error) {
      const errorMessage = `Session refresh error: ${error instanceof Error ? error.message : 'Unknown error'}`
      setAuthState(prev => ({ ...prev, error: errorMessage }))
    }
  }, [fetchUserProfile])

  // Refresh user profile
  const refreshProfile = useCallback(async () => {
    if (!authState.user) return

    try {
      const profile = await fetchUserProfile(authState.user.id)
      if (profile) {
        setAuthState(prev => ({ ...prev, profile }))
      }
    } catch (error) {
      console.error('Error refreshing profile:', error)
    }
  }, [authState.user, fetchUserProfile])

  // Context value
  const value: AuthContextType = {
    user: authState.user,
    session: authState.session,
    profile: authState.profile,
    loading: authState.loading,
    error: authState.error,
    signInWithGoogle,
    signOut,
    clearError,
    refreshSession,
    refreshProfile
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