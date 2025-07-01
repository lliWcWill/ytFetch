import React from 'react'
import { render as rtlRender } from '@testing-library/react'
import { AuthProvider } from '@/providers/AuthProvider'
import type { User, Session } from '@supabase/supabase-js'

// Mock user factory
export function createMockUser(overrides?: Partial<User>): User {
  return {
    id: 'test-user-123',
    email: 'test@example.com',
    app_metadata: {},
    user_metadata: {},
    aud: 'authenticated',
    created_at: '2024-01-01T00:00:00Z',
    confirmed_at: '2024-01-01T00:00:00Z',
    email_confirmed_at: '2024-01-01T00:00:00Z',
    phone: null,
    last_sign_in_at: '2024-01-01T00:00:00Z',
    role: 'authenticated',
    updated_at: '2024-01-01T00:00:00Z',
    identities: [],
    factors: [],
    ...overrides,
  }
}

// Mock session factory
export function createMockSession(overrides?: Partial<Session>): Session {
  const user = overrides?.user || createMockUser()
  return {
    access_token: 'mock-access-token',
    refresh_token: 'mock-refresh-token',
    expires_in: 3600,
    expires_at: Math.floor(Date.now() / 1000) + 3600,
    token_type: 'bearer',
    user,
    ...overrides,
  }
}

// Custom render function with AuthProvider
interface RenderOptions {
  initialAuth?: {
    user?: User | null
    session?: Session | null
    loading?: boolean
    error?: string | null
  }
  wrapper?: React.ComponentType
}

export function renderWithAuth(
  ui: React.ReactElement,
  options?: RenderOptions
) {
  const { initialAuth, ...renderOptions } = options || {}

  // Create a wrapper that includes AuthProvider
  const Wrapper = ({ children }: { children: React.ReactNode }) => {
    // If we need to mock initial auth state, we'd need to modify AuthProvider
    // For now, we'll use the real AuthProvider
    return <AuthProvider>{children}</AuthProvider>
  }

  return rtlRender(ui, { wrapper: Wrapper, ...renderOptions })
}

// Helper to wait for auth state
export async function waitForAuthState(
  expectedState: 'authenticated' | 'unauthenticated',
  timeout = 5000
) {
  const startTime = Date.now()
  
  return new Promise<void>((resolve, reject) => {
    const checkInterval = setInterval(() => {
      // This would check the actual auth state
      // For testing purposes, we'd need to expose auth state somehow
      
      if (Date.now() - startTime > timeout) {
        clearInterval(checkInterval)
        reject(new Error(`Timeout waiting for auth state: ${expectedState}`))
      }
    }, 100)
  })
}

// Mock auth context for isolated component testing
export function createMockAuthContext(overrides?: Partial<any>) {
  return {
    user: null,
    session: null,
    profile: null,
    loading: false,
    error: null,
    signInWithGoogle: jest.fn().mockResolvedValue({ error: null }),
    signOut: jest.fn().mockResolvedValue(undefined),
    clearError: jest.fn(),
    refreshSession: jest.fn().mockResolvedValue(undefined),
    refreshProfile: jest.fn().mockResolvedValue(undefined),
    ...overrides,
  }
}

// Helper to simulate auth state changes
export class AuthStateMocker {
  private callbacks: ((event: any, session: any) => void)[] = []

  onAuthStateChange(callback: (event: any, session: any) => void) {
    this.callbacks.push(callback)
    return {
      data: { subscription: { unsubscribe: jest.fn() } },
    }
  }

  triggerSignIn(user?: Partial<User>) {
    const session = createMockSession({ user: createMockUser(user) })
    this.callbacks.forEach(cb => cb('SIGNED_IN', session))
  }

  triggerSignOut() {
    this.callbacks.forEach(cb => cb('SIGNED_OUT', null))
  }

  triggerTokenRefresh(session?: Partial<Session>) {
    const newSession = createMockSession(session)
    this.callbacks.forEach(cb => cb('TOKEN_REFRESHED', newSession))
  }

  triggerError(error: string) {
    this.callbacks.forEach(cb => cb('USER_UPDATED', null))
  }
}

// Helper to test protected routes
export async function testProtectedRoute(
  routePath: string,
  expectedRedirect: string = '/login'
) {
  // This would test that unauthenticated users are redirected
  // Implementation would depend on how middleware is set up
}

// Helper to test auth persistence
export function setupAuthPersistence(session?: Session) {
  const storage = {
    getItem: jest.fn(),
    setItem: jest.fn(),
    removeItem: jest.fn(),
    clear: jest.fn(),
    key: jest.fn(),
    length: 0,
  }

  if (session) {
    storage.getItem.mockReturnValue(JSON.stringify(session))
  }

  Object.defineProperty(window, 'localStorage', {
    value: storage,
    writable: true,
  })

  return storage
}

// Helper for testing OAuth flows
export class OAuthFlowMocker {
  private redirectUrl: string | null = null

  mockSignInWithOAuth() {
    return jest.fn().mockImplementation(({ options }) => {
      this.redirectUrl = options?.redirectTo || null
      // Simulate redirect
      if (options?.redirectTo) {
        window.location.href = options.redirectTo
      }
      return Promise.resolve({ error: null })
    })
  }

  getRedirectUrl() {
    return this.redirectUrl
  }

  simulateCallback(code: string) {
    const url = new URL(window.location.href)
    url.searchParams.set('code', code)
    window.history.pushState({}, '', url.toString())
  }
}

// Export test IDs for consistent testing
export const AUTH_TEST_IDS = {
  signInButton: 'auth-sign-in-button',
  signOutButton: 'auth-sign-out-button',
  userMenu: 'auth-user-menu',
  userEmail: 'auth-user-email',
  errorMessage: 'auth-error-message',
  loadingSpinner: 'auth-loading-spinner',
} as const