import React from 'react'
import { render, waitFor, act, renderHook } from '@testing-library/react'
import { AuthProvider, useAuth } from '../AuthProvider'
import { createClient } from '@/utils/supabase/client'
import type { AuthChangeEvent } from '@supabase/supabase-js'

// Mock the Supabase client
jest.mock('@/utils/supabase/client')

describe('AuthProvider', () => {
  let mockSupabaseClient: any
  let authStateChangeCallback: ((event: AuthChangeEvent, session: any) => void) | null = null

  beforeEach(() => {
    jest.clearAllMocks()
    
    // Reset window.dispatchEvent mock
    (window.dispatchEvent as jest.Mock).mockClear()
    
    // Setup mock Supabase client
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

  describe('Initial State', () => {
    it('should initialize with loading state', () => {
      const { result } = renderHook(() => useAuth(), {
        wrapper: ({ children }) => <AuthProvider>{children}</AuthProvider>,
      })

      expect(result.current.loading).toBe(true)
      expect(result.current.user).toBeNull()
      expect(result.current.session).toBeNull()
      expect(result.current.error).toBeNull()
    })

    it('should fetch initial session on mount', async () => {
      renderHook(() => useAuth(), {
        wrapper: ({ children }) => <AuthProvider>{children}</AuthProvider>,
      })

      await waitFor(() => {
        expect(mockSupabaseClient.auth.getSession).toHaveBeenCalled()
      })
    })
  })

  describe('Auth State Changes', () => {
    it('should update state when user signs in', async () => {
      const { result } = renderHook(() => useAuth(), {
        wrapper: ({ children }) => <AuthProvider>{children}</AuthProvider>,
      })

      const mockSession = {
        user: { id: '123', email: 'test@example.com' },
        access_token: 'token123',
      }

      // Simulate sign in
      act(() => {
        authStateChangeCallback?.('SIGNED_IN', mockSession)
      })

      await waitFor(() => {
        expect(result.current.user).toEqual(mockSession.user)
        expect(result.current.session).toEqual(mockSession)
        expect(result.current.loading).toBe(false)
      })

      // Check that auth-state-changed event was dispatched
      expect(window.dispatchEvent).toHaveBeenCalledWith(
        expect.objectContaining({ type: 'auth-state-changed' })
      )
    })

    it('should update state when user signs out', async () => {
      const { result } = renderHook(() => useAuth(), {
        wrapper: ({ children }) => <AuthProvider>{children}</AuthProvider>,
      })

      // First sign in
      const mockSession = {
        user: { id: '123', email: 'test@example.com' },
        access_token: 'token123',
      }
      
      act(() => {
        authStateChangeCallback?.('SIGNED_IN', mockSession)
      })

      // Then sign out
      act(() => {
        authStateChangeCallback?.('SIGNED_OUT', null)
      })

      await waitFor(() => {
        expect(result.current.user).toBeNull()
        expect(result.current.session).toBeNull()
        expect(result.current.loading).toBe(false)
      })

      // Check that auth-state-changed event was dispatched
      expect(window.dispatchEvent).toHaveBeenCalledWith(
        expect.objectContaining({ type: 'auth-state-changed' })
      )
    })

    it('should handle token refresh', async () => {
      const { result } = renderHook(() => useAuth(), {
        wrapper: ({ children }) => <AuthProvider>{children}</AuthProvider>,
      })

      const mockSession = {
        user: { id: '123', email: 'test@example.com' },
        access_token: 'new_token123',
      }

      act(() => {
        authStateChangeCallback?.('TOKEN_REFRESHED', mockSession)
      })

      await waitFor(() => {
        expect(result.current.session).toEqual(mockSession)
      })
    })
  })

  describe('Auth Methods', () => {
    it('should handle Google sign in', async () => {
      const { result } = renderHook(() => useAuth(), {
        wrapper: ({ children }) => <AuthProvider>{children}</AuthProvider>,
      })

      mockSupabaseClient.auth.signInWithOAuth.mockResolvedValue({ error: null })

      await act(async () => {
        await result.current.signInWithGoogle()
      })

      expect(mockSupabaseClient.auth.signInWithOAuth).toHaveBeenCalledWith({
        provider: 'google',
        options: {
          redirectTo: expect.stringContaining('/auth/callback'),
          queryParams: {
            access_type: 'offline',
            prompt: 'consent',
          },
        },
      })
    })

    it('should handle sign in error', async () => {
      const { result } = renderHook(() => useAuth(), {
        wrapper: ({ children }) => <AuthProvider>{children}</AuthProvider>,
      })

      const mockError = { message: 'Sign in failed' }
      mockSupabaseClient.auth.signInWithOAuth.mockResolvedValue({ error: mockError })

      await act(async () => {
        const response = await result.current.signInWithGoogle()
        expect(response.error).toEqual(mockError)
      })

      expect(result.current.error).toBe('Sign in failed')
    })

    it('should handle sign out', async () => {
      const { result } = renderHook(() => useAuth(), {
        wrapper: ({ children }) => <AuthProvider>{children}</AuthProvider>,
      })

      mockSupabaseClient.auth.signOut.mockResolvedValue({ error: null })

      await act(async () => {
        await result.current.signOut()
      })

      expect(mockSupabaseClient.auth.signOut).toHaveBeenCalled()
    })

    it('should clear error', async () => {
      const { result } = renderHook(() => useAuth(), {
        wrapper: ({ children }) => <AuthProvider>{children}</AuthProvider>,
      })

      // Set an error first
      act(() => {
        authStateChangeCallback?.('SIGNED_IN', null)
      })

      await waitFor(() => {
        expect(result.current.error).toBeTruthy()
      })

      // Clear the error
      act(() => {
        result.current.clearError()
      })

      expect(result.current.error).toBeNull()
    })
  })

  describe('Session Refresh', () => {
    it('should refresh session', async () => {
      const { result } = renderHook(() => useAuth(), {
        wrapper: ({ children }) => <AuthProvider>{children}</AuthProvider>,
      })

      const mockSession = {
        user: { id: '123', email: 'test@example.com' },
        access_token: 'token123',
      }

      mockSupabaseClient.auth.getSession.mockResolvedValue({
        data: { session: mockSession },
        error: null,
      })

      await act(async () => {
        await result.current.refreshSession()
      })

      expect(mockSupabaseClient.auth.getSession).toHaveBeenCalled()
      expect(result.current.session).toEqual(mockSession)
    })
  })

  describe('Error Handling', () => {
    it('should throw error when useAuth is used outside provider', () => {
      // Suppress console.error for this test
      const originalError = console.error
      console.error = jest.fn()

      expect(() => {
        renderHook(() => useAuth())
      }).toThrow('useAuth must be used within an AuthProvider')

      console.error = originalError
    })
  })
})