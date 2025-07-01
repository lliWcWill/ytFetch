import React from 'react'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import Header from '../Header'
import { useAuth } from '@/providers/AuthProvider'
import { useRouter, usePathname } from 'next/navigation'

// Mock dependencies
jest.mock('@/providers/AuthProvider')
jest.mock('next/navigation')
jest.mock('@/components/TokenBalance', () => ({
  TokenBalance: () => <div data-testid="token-balance">Token Balance</div>,
}))

describe('Header Component', () => {
  const mockUseAuth = useAuth as jest.MockedFunction<typeof useAuth>
  const mockUseRouter = useRouter as jest.MockedFunction<typeof useRouter>
  const mockUsePathname = usePathname as jest.MockedFunction<typeof usePathname>
  
  let mockRouter: any
  let mockAuthContext: any

  beforeEach(() => {
    jest.clearAllMocks()
    
    // Setup router mock
    mockRouter = {
      push: jest.fn(),
      replace: jest.fn(),
      refresh: jest.fn(),
    }
    mockUseRouter.mockReturnValue(mockRouter)
    mockUsePathname.mockReturnValue('/')

    // Default auth context (unauthenticated)
    mockAuthContext = {
      user: null,
      session: null,
      profile: null,
      loading: false,
      error: null,
      signInWithGoogle: jest.fn(),
      signOut: jest.fn(),
      clearError: jest.fn(),
      refreshSession: jest.fn(),
      refreshProfile: jest.fn(),
    }
    mockUseAuth.mockReturnValue(mockAuthContext)
  })

  describe('Unauthenticated State', () => {
    it('should show sign in button when user is not authenticated', () => {
      render(<Header />)
      
      expect(screen.getByText('Sign In')).toBeInTheDocument()
      expect(screen.queryByTestId('token-balance')).not.toBeInTheDocument()
    })

    it('should navigate to login when sign in is clicked', () => {
      render(<Header />)
      
      const signInButton = screen.getByText('Sign In')
      fireEvent.click(signInButton)
      
      expect(mockRouter.push).toHaveBeenCalledWith('/login')
    })
  })

  describe('Authenticated State', () => {
    beforeEach(() => {
      mockAuthContext.user = {
        id: '123',
        email: 'test@example.com',
        app_metadata: {},
        user_metadata: {},
        aud: 'authenticated',
        created_at: '2024-01-01',
      }
      mockAuthContext.session = {
        access_token: 'token123',
        refresh_token: 'refresh123',
        expires_in: 3600,
        token_type: 'bearer',
        user: mockAuthContext.user,
      }
    })

    it('should show user menu and token balance when authenticated', () => {
      render(<Header />)
      
      expect(screen.queryByText('Sign In')).not.toBeInTheDocument()
      expect(screen.getByTestId('token-balance')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /user menu/i })).toBeInTheDocument()
    })

    it('should show user email in dropdown menu', async () => {
      render(<Header />)
      
      const userMenuButton = screen.getByRole('button', { name: /user menu/i })
      fireEvent.click(userMenuButton)
      
      await waitFor(() => {
        expect(screen.getByText('test@example.com')).toBeInTheDocument()
      })
    })

    it('should handle sign out', async () => {
      render(<Header />)
      
      // Open user menu
      const userMenuButton = screen.getByRole('button', { name: /user menu/i })
      fireEvent.click(userMenuButton)
      
      // Click sign out
      const signOutButton = await screen.findByText('Sign Out')
      fireEvent.click(signOutButton)
      
      expect(mockAuthContext.signOut).toHaveBeenCalled()
    })

    it('should navigate to profile settings', async () => {
      render(<Header />)
      
      // Open user menu
      const userMenuButton = screen.getByRole('button', { name: /user menu/i })
      fireEvent.click(userMenuButton)
      
      // Click profile
      const profileLink = await screen.findByText('Profile')
      fireEvent.click(profileLink)
      
      expect(mockRouter.push).toHaveBeenCalledWith('/profile')
    })

    it('should navigate to billing', async () => {
      render(<Header />)
      
      // Open user menu
      const userMenuButton = screen.getByRole('button', { name: /user menu/i })
      fireEvent.click(userMenuButton)
      
      // Click billing
      const billingLink = await screen.findByText('Billing')
      fireEvent.click(billingLink)
      
      expect(mockRouter.push).toHaveBeenCalledWith('/billing')
    })
  })

  describe('Auth State Change Events', () => {
    it('should re-render when auth-state-changed event is dispatched', async () => {
      const { rerender } = render(<Header />)
      
      // Initially unauthenticated
      expect(screen.getByText('Sign In')).toBeInTheDocument()
      
      // Update auth context to authenticated
      mockAuthContext.user = {
        id: '123',
        email: 'test@example.com',
        app_metadata: {},
        user_metadata: {},
        aud: 'authenticated',
        created_at: '2024-01-01',
      }
      
      // Dispatch auth state change event
      window.dispatchEvent(new Event('auth-state-changed'))
      
      // Re-render should happen automatically due to event listener
      rerender(<Header />)
      
      await waitFor(() => {
        expect(screen.queryByText('Sign In')).not.toBeInTheDocument()
        expect(screen.getByTestId('token-balance')).toBeInTheDocument()
      })
    })

    it('should cleanup event listener on unmount', () => {
      const removeEventListenerSpy = jest.spyOn(window, 'removeEventListener')
      
      const { unmount } = render(<Header />)
      unmount()
      
      expect(removeEventListenerSpy).toHaveBeenCalledWith(
        'auth-state-changed',
        expect.any(Function)
      )
    })
  })

  describe('Loading State', () => {
    it('should show loading state while auth is loading', () => {
      mockAuthContext.loading = true
      render(<Header />)
      
      // Should not show sign in button or user menu while loading
      expect(screen.queryByText('Sign In')).not.toBeInTheDocument()
      expect(screen.queryByRole('button', { name: /user menu/i })).not.toBeInTheDocument()
    })
  })

  describe('Mobile Menu', () => {
    it('should toggle mobile menu', async () => {
      render(<Header />)
      
      // Mobile menu should be hidden initially
      expect(screen.queryByRole('navigation', { name: /mobile/i })).not.toBeInTheDocument()
      
      // Click menu button
      const menuButton = screen.getByRole('button', { name: /menu/i })
      fireEvent.click(menuButton)
      
      // Mobile menu should be visible
      await waitFor(() => {
        expect(screen.getByRole('navigation', { name: /mobile/i })).toBeInTheDocument()
      })
      
      // Click close button
      const closeButton = screen.getByRole('button', { name: /close/i })
      fireEvent.click(closeButton)
      
      // Mobile menu should be hidden again
      await waitFor(() => {
        expect(screen.queryByRole('navigation', { name: /mobile/i })).not.toBeInTheDocument()
      })
    })
  })

  describe('Navigation Links', () => {
    it('should highlight active navigation link', () => {
      mockUsePathname.mockReturnValue('/bulk')
      render(<Header />)
      
      const bulkLink = screen.getByRole('link', { name: /bulk process/i })
      expect(bulkLink).toHaveClass('text-primary')
    })
  })

  describe('Profile Dropdown', () => {
    beforeEach(() => {
      mockAuthContext.user = {
        id: '123',
        email: 'test@example.com',
        app_metadata: {},
        user_metadata: {},
        aud: 'authenticated',
        created_at: '2024-01-01',
      }
    })

    it('should close dropdown when clicking outside', async () => {
      render(
        <div>
          <Header />
          <div data-testid="outside">Outside content</div>
        </div>
      )
      
      // Open dropdown
      const userMenuButton = screen.getByRole('button', { name: /user menu/i })
      fireEvent.click(userMenuButton)
      
      // Verify dropdown is open
      await waitFor(() => {
        expect(screen.getByText('test@example.com')).toBeInTheDocument()
      })
      
      // Click outside
      fireEvent.mouseDown(screen.getByTestId('outside'))
      
      // Dropdown should close
      await waitFor(() => {
        expect(screen.queryByText('test@example.com')).not.toBeInTheDocument()
      })
    })
  })
})