import React from 'react'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { act } from 'react'
import type { AuthChangeEvent } from '@supabase/supabase-js'

// Mock all the required modules
jest.mock('next/navigation')
jest.mock('@/utils/supabase/client')
jest.mock('@/utils/supabase/server')
jest.mock('@stripe/stripe-js')

// Import components and utilities
import { AuthProvider, useAuth } from '@/providers/AuthProvider'
import Header from '@/components/Header'
import { createClient } from '@/utils/supabase/client'
import { useRouter } from 'next/navigation'

describe('Complete Auth Flow Integration', () => {
  let mockSupabaseClient: any
  let authStateChangeCallback: ((event: AuthChangeEvent, session: any) => void) | null = null
  let mockRouter: any

  beforeEach(() => {
    jest.clearAllMocks()
    
    // Setup router mock
    mockRouter = {
      push: jest.fn(),
      replace: jest.fn(),
      refresh: jest.fn(),
    }
    ;(useRouter as jest.Mock).mockReturnValue(mockRouter)

    // Setup Supabase mock
    mockSupabaseClient = {
      auth: {
        getSession: jest.fn().mockResolvedValue({ data: { session: null }, error: null }),
        getUser: jest.fn().mockResolvedValue({ data: { user: null }, error: null }),
        onAuthStateChange: jest.fn((callback) => {
          authStateChangeCallback = callback
          return {
            data: { subscription: { unsubscribe: jest.fn() } },
          }
        }),
        signInWithOAuth: jest.fn(),
        signOut: jest.fn(),
      },
    }
    ;(createClient as jest.Mock).mockReturnValue(mockSupabaseClient)
  })

  describe('End-to-End Auth Flow', () => {
    it('should complete full auth flow: sign in → state update → UI update', async () => {
      // Test component that uses auth
      const TestApp = () => {
        return (
          <AuthProvider>
            <Header />
            <AuthStateDisplay />
          </AuthProvider>
        )
      }

      // Component to display auth state
      const AuthStateDisplay = () => {
        const { user, loading } = useAuth()
        
        if (loading) return <div>Loading...</div>
        
        return (
          <div data-testid="auth-state">
            {user ? `Logged in as ${user.email}` : 'Not logged in'}
          </div>
        )
      }

      render(<TestApp />)

      // Initial state - not logged in
      await waitFor(() => {
        expect(screen.getByTestId('auth-state')).toHaveTextContent('Not logged in')
        expect(screen.getByText('Sign In')).toBeInTheDocument()
      })

      // Click sign in
      fireEvent.click(screen.getByText('Sign In'))
      expect(mockRouter.push).toHaveBeenCalledWith('/login')

      // Simulate successful OAuth sign in
      mockSupabaseClient.auth.signInWithOAuth.mockResolvedValue({ error: null })
      
      // Simulate auth state change to signed in
      const mockUser = {
        id: '123',
        email: 'test@example.com',
        app_metadata: {},
        user_metadata: {},
        aud: 'authenticated',
        created_at: '2024-01-01',
      }
      
      const mockSession = {
        user: mockUser,
        access_token: 'token123',
        refresh_token: 'refresh123',
        expires_in: 3600,
        token_type: 'bearer',
      }

      act(() => {
        authStateChangeCallback?.('SIGNED_IN', mockSession)
      })

      // Wait for UI to update
      await waitFor(() => {
        expect(screen.getByTestId('auth-state')).toHaveTextContent('Logged in as test@example.com')
        expect(screen.queryByText('Sign In')).not.toBeInTheDocument()
        expect(screen.getByRole('button', { name: /user menu/i })).toBeInTheDocument()
      })

      // Verify auth state change event was dispatched
      expect(window.dispatchEvent).toHaveBeenCalledWith(
        expect.objectContaining({ type: 'auth-state-changed' })
      )
    })

    it('should handle auth flow with redirect preservation', async () => {
      // Component that redirects to login with intended destination
      const ProtectedComponent = () => {
        const { user, signInWithGoogle } = useAuth()
        const router = useRouter()
        
        React.useEffect(() => {
          if (!user) {
            router.push('/login?redirect_to=/billing')
          }
        }, [user, router])
        
        const handleSignIn = async () => {
          await signInWithGoogle()
        }
        
        return (
          <div>
            {!user && <button onClick={handleSignIn}>Sign In to Continue</button>}
            {user && <div>Welcome to Billing</div>}
          </div>
        )
      }

      const TestApp = () => (
        <AuthProvider>
          <ProtectedComponent />
        </AuthProvider>
      )

      render(<TestApp />)

      // Should redirect to login
      await waitFor(() => {
        expect(mockRouter.push).toHaveBeenCalledWith('/login?redirect_to=/billing')
      })

      // Mock the OAuth redirect URL to include the redirect parameter
      mockSupabaseClient.auth.signInWithOAuth.mockImplementation(({ options }) => {
        expect(options.redirectTo).toContain('/auth/callback')
        expect(options.redirectTo).toContain('next=%2Fbilling')
        return Promise.resolve({ error: null })
      })

      // Click sign in
      fireEvent.click(screen.getByText('Sign In to Continue'))

      // Verify OAuth was called with correct redirect
      expect(mockSupabaseClient.auth.signInWithOAuth).toHaveBeenCalled()
    })

    it('should handle sign out flow correctly', async () => {
      const TestApp = () => (
        <AuthProvider>
          <Header />
        </AuthProvider>
      )

      render(<TestApp />)

      // Set up authenticated state
      const mockSession = {
        user: { id: '123', email: 'test@example.com' },
        access_token: 'token123',
      }

      act(() => {
        authStateChangeCallback?.('SIGNED_IN', mockSession)
      })

      // Wait for authenticated UI
      await waitFor(() => {
        expect(screen.getByRole('button', { name: /user menu/i })).toBeInTheDocument()
      })

      // Open user menu and sign out
      fireEvent.click(screen.getByRole('button', { name: /user menu/i }))
      
      const signOutButton = await screen.findByText('Sign Out')
      
      mockSupabaseClient.auth.signOut.mockResolvedValue({ error: null })
      
      fireEvent.click(signOutButton)

      // Simulate sign out event
      act(() => {
        authStateChangeCallback?.('SIGNED_OUT', null)
      })

      // UI should update to show sign in button
      await waitFor(() => {
        expect(screen.getByText('Sign In')).toBeInTheDocument()
        expect(screen.queryByRole('button', { name: /user menu/i })).not.toBeInTheDocument()
      })

      // Verify auth state change event was dispatched
      expect(window.dispatchEvent).toHaveBeenCalledWith(
        expect.objectContaining({ type: 'auth-state-changed' })
      )
    })

    it('should handle auth errors gracefully', async () => {
      const TestApp = () => {
        const { error, clearError } = useAuth()
        
        return (
          <AuthProvider>
            {error && (
              <div role="alert">
                {error}
                <button onClick={clearError}>Dismiss</button>
              </div>
            )}
            <Header />
          </AuthProvider>
        )
      }

      const AuthErrorComponent = () => {
        const { error, clearError, signInWithGoogle } = useAuth()
        
        return (
          <div>
            {error && (
              <div role="alert">
                {error}
                <button onClick={clearError}>Dismiss</button>
              </div>
            )}
            <button onClick={signInWithGoogle}>Try Sign In</button>
          </div>
        )
      }

      render(
        <AuthProvider>
          <AuthErrorComponent />
        </AuthProvider>
      )

      // Mock sign in error
      mockSupabaseClient.auth.signInWithOAuth.mockResolvedValue({
        error: { message: 'Authentication failed' },
      })

      // Try to sign in
      fireEvent.click(screen.getByText('Try Sign In'))

      // Error should be displayed
      await waitFor(() => {
        expect(screen.getByRole('alert')).toHaveTextContent('Authentication failed')
      })

      // Clear error
      fireEvent.click(screen.getByText('Dismiss'))

      // Error should be cleared
      await waitFor(() => {
        expect(screen.queryByRole('alert')).not.toBeInTheDocument()
      })
    })
  })

  describe('Concurrent Auth Operations', () => {
    it('should handle rapid auth state changes', async () => {
      const TestApp = () => (
        <AuthProvider>
          <AuthStateDisplay />
        </AuthProvider>
      )

      const AuthStateDisplay = () => {
        const { user, session } = useAuth()
        return (
          <div>
            <div data-testid="user-state">{user ? 'Authenticated' : 'Guest'}</div>
            <div data-testid="session-state">{session ? 'Active' : 'None'}</div>
          </div>
        )
      }

      render(<TestApp />)

      // Rapid auth state changes
      const mockSession1 = {
        user: { id: '1', email: 'user1@example.com' },
        access_token: 'token1',
      }

      const mockSession2 = {
        user: { id: '2', email: 'user2@example.com' },
        access_token: 'token2',
      }

      // Simulate rapid state changes
      act(() => {
        authStateChangeCallback?.('SIGNED_IN', mockSession1)
        authStateChangeCallback?.('SIGNED_OUT', null)
        authStateChangeCallback?.('SIGNED_IN', mockSession2)
      })

      // Final state should be the last one
      await waitFor(() => {
        expect(screen.getByTestId('user-state')).toHaveTextContent('Authenticated')
        expect(screen.getByTestId('session-state')).toHaveTextContent('Active')
      })
    })
  })

  describe('Auth Persistence', () => {
    it('should restore session on mount', async () => {
      // Mock existing session
      mockSupabaseClient.auth.getSession.mockResolvedValue({
        data: {
          session: {
            user: { id: '123', email: 'existing@example.com' },
            access_token: 'existing_token',
          },
        },
        error: null,
      })

      const TestApp = () => {
        const { user, loading } = useAuth()
        
        if (loading) return <div>Loading...</div>
        
        return (
          <div data-testid="user-email">
            {user?.email || 'No user'}
          </div>
        )
      }

      render(
        <AuthProvider>
          <TestApp />
        </AuthProvider>
      )

      // Should restore existing session
      await waitFor(() => {
        expect(screen.getByTestId('user-email')).toHaveTextContent('existing@example.com')
      })
    })
  })
})