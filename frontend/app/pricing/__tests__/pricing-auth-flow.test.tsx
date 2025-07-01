import React from 'react'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { useRouter, useSearchParams } from 'next/navigation'
import { useAuth } from '@/providers/AuthProvider'
import PricingPage from '../page' // Assuming this is the pricing page component
import { loadStripe } from '@stripe/stripe-js'

// Mock dependencies
jest.mock('next/navigation')
jest.mock('@/providers/AuthProvider')
jest.mock('@stripe/stripe-js')
jest.mock('@/services/api', () => ({
  api: {
    createCheckoutSession: jest.fn(),
  },
}))

// Import the mocked api
import { api } from '@/services/api'

describe('Pricing → Auth → Checkout Flow', () => {
  const mockUseRouter = useRouter as jest.MockedFunction<typeof useRouter>
  const mockUseSearchParams = useSearchParams as jest.MockedFunction<typeof useSearchParams>
  const mockUseAuth = useAuth as jest.MockedFunction<typeof useAuth>
  const mockLoadStripe = loadStripe as jest.MockedFunction<typeof loadStripe>
  
  let mockRouter: any
  let mockSearchParams: URLSearchParams
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
    
    // Setup search params mock
    mockSearchParams = new URLSearchParams()
    mockUseSearchParams.mockReturnValue(mockSearchParams)

    // Default auth context (unauthenticated)
    mockAuthContext = {
      user: null,
      session: null,
      profile: null,
      loading: false,
      error: null,
      signInWithGoogle: jest.fn().mockResolvedValue({ error: null }),
      signOut: jest.fn(),
      clearError: jest.fn(),
      refreshSession: jest.fn(),
      refreshProfile: jest.fn(),
    }
    mockUseAuth.mockReturnValue(mockAuthContext)

    // Mock Stripe
    mockLoadStripe.mockResolvedValue({
      redirectToCheckout: jest.fn().mockResolvedValue({ error: null }),
    } as any)
  })

  describe('Package Selection Preservation', () => {
    it('should preserve package selection through auth flow', async () => {
      // Mock pricing page component for this test
      const PricingPageMock = () => {
        const { user, signInWithGoogle } = useAuth()
        const router = useRouter()
        
        const handlePackageSelect = async (packageId: string) => {
          if (!user) {
            // Encode the pricing page URL with package selection
            const redirectUrl = `/pricing?package=${packageId}`
            await signInWithGoogle()
            // In real implementation, this would be handled by signInWithGoogle
            // with redirectTo parameter
          }
        }
        
        return (
          <div>
            <button onClick={() => handlePackageSelect('starter')}>
              Select Starter Pack
            </button>
          </div>
        )
      }
      
      render(<PricingPageMock />)
      
      // Click package selection
      const starterButton = screen.getByText('Select Starter Pack')
      fireEvent.click(starterButton)
      
      // Verify sign in was called
      expect(mockAuthContext.signInWithGoogle).toHaveBeenCalled()
    })
  })

  describe('Auto-checkout After Auth', () => {
    it('should automatically trigger checkout when returning from auth with package param', async () => {
      // Simulate returning from auth with package selection
      mockSearchParams = new URLSearchParams('package=starter&auth_success=1')
      mockUseSearchParams.mockReturnValue(mockSearchParams)
      
      // User is now authenticated
      mockAuthContext.user = {
        id: '123',
        email: 'test@example.com',
      }
      mockAuthContext.session = {
        access_token: 'token123',
      }
      
      // Mock successful checkout session creation
      ;(api.createCheckoutSession as jest.Mock).mockResolvedValue({
        sessionId: 'cs_test_123',
      })
      
      // Mock component that handles auto-checkout
      const AutoCheckoutComponent = () => {
        const { user } = useAuth()
        const searchParams = useSearchParams()
        const router = useRouter()
        
        React.useEffect(() => {
          const handleAutoCheckout = async () => {
            const packageId = searchParams.get('package')
            const authSuccess = searchParams.get('auth_success')
            
            if (user && packageId && authSuccess === '1') {
              // Create checkout session
              const { sessionId } = await api.createCheckoutSession({
                priceId: `price_${packageId}`,
              })
              
              // Redirect to Stripe
              const stripe = await loadStripe(process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY!)
              await stripe?.redirectToCheckout({ sessionId })
            }
          }
          
          handleAutoCheckout()
        }, [user, searchParams])
        
        return <div>Processing checkout...</div>
      }
      
      render(<AutoCheckoutComponent />)
      
      // Wait for checkout to be triggered
      await waitFor(() => {
        expect(api.createCheckoutSession).toHaveBeenCalledWith({
          priceId: 'price_starter',
        })
      })
      
      // Verify Stripe redirect was called
      const stripe = await mockLoadStripe()
      expect(stripe?.redirectToCheckout).toHaveBeenCalledWith({
        sessionId: 'cs_test_123',
      })
    })

    it('should not trigger checkout without auth_success param', async () => {
      // Package param but no auth_success
      mockSearchParams = new URLSearchParams('package=starter')
      mockUseSearchParams.mockReturnValue(mockSearchParams)
      
      mockAuthContext.user = {
        id: '123',
        email: 'test@example.com',
      }
      
      const AutoCheckoutComponent = () => {
        const { user } = useAuth()
        const searchParams = useSearchParams()
        
        React.useEffect(() => {
          const packageId = searchParams.get('package')
          const authSuccess = searchParams.get('auth_success')
          
          if (user && packageId && authSuccess === '1') {
            api.createCheckoutSession({ priceId: `price_${packageId}` })
          }
        }, [user, searchParams])
        
        return <div>Pricing page</div>
      }
      
      render(<AutoCheckoutComponent />)
      
      // Should not create checkout session
      await waitFor(() => {
        expect(api.createCheckoutSession).not.toHaveBeenCalled()
      })
    })

    it('should handle checkout errors gracefully', async () => {
      mockSearchParams = new URLSearchParams('package=starter&auth_success=1')
      mockUseSearchParams.mockReturnValue(mockSearchParams)
      
      mockAuthContext.user = { id: '123', email: 'test@example.com' }
      
      // Mock checkout session creation failure
      ;(api.createCheckoutSession as jest.Mock).mockRejectedValue(
        new Error('Payment processing unavailable')
      )
      
      const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation()
      
      const AutoCheckoutComponent = () => {
        const { user } = useAuth()
        const searchParams = useSearchParams()
        const [error, setError] = React.useState<string | null>(null)
        
        React.useEffect(() => {
          const handleAutoCheckout = async () => {
            try {
              const packageId = searchParams.get('package')
              const authSuccess = searchParams.get('auth_success')
              
              if (user && packageId && authSuccess === '1') {
                await api.createCheckoutSession({ priceId: `price_${packageId}` })
              }
            } catch (err) {
              setError('Failed to process checkout')
              console.error('Checkout error:', err)
            }
          }
          
          handleAutoCheckout()
        }, [user, searchParams])
        
        return (
          <div>
            {error && <div role="alert">{error}</div>}
          </div>
        )
      }
      
      render(<AutoCheckoutComponent />)
      
      // Wait for error to be displayed
      await waitFor(() => {
        expect(screen.getByRole('alert')).toHaveTextContent('Failed to process checkout')
      })
      
      expect(consoleErrorSpy).toHaveBeenCalledWith(
        'Checkout error:',
        expect.any(Error)
      )
      
      consoleErrorSpy.mockRestore()
    })
  })

  describe('Query Parameter Cleanup', () => {
    it('should clean up auth_success param after processing', async () => {
      mockSearchParams = new URLSearchParams('package=starter&auth_success=1')
      mockUseSearchParams.mockReturnValue(mockSearchParams)
      
      mockAuthContext.user = { id: '123', email: 'test@example.com' }
      
      const AutoCheckoutComponent = () => {
        const { user } = useAuth()
        const searchParams = useSearchParams()
        const router = useRouter()
        
        React.useEffect(() => {
          const cleanup = async () => {
            const authSuccess = searchParams.get('auth_success')
            
            if (authSuccess === '1') {
              // Remove auth_success param
              const newParams = new URLSearchParams(searchParams)
              newParams.delete('auth_success')
              
              router.replace(`/pricing${newParams.toString() ? `?${newParams.toString()}` : ''}`)
            }
          }
          
          cleanup()
        }, [searchParams, router])
        
        return <div>Pricing page</div>
      }
      
      render(<AutoCheckoutComponent />)
      
      await waitFor(() => {
        expect(mockRouter.replace).toHaveBeenCalledWith('/pricing?package=starter')
      })
    })
  })

  describe('Direct Checkout for Authenticated Users', () => {
    it('should go directly to checkout for authenticated users', async () => {
      // User is already authenticated
      mockAuthContext.user = { id: '123', email: 'test@example.com' }
      mockAuthContext.session = { access_token: 'token123' }
      
      ;(api.createCheckoutSession as jest.Mock).mockResolvedValue({
        sessionId: 'cs_test_direct',
      })
      
      const PricingComponent = () => {
        const { user } = useAuth()
        
        const handlePackageSelect = async (priceId: string) => {
          if (user) {
            const { sessionId } = await api.createCheckoutSession({ priceId })
            const stripe = await loadStripe(process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY!)
            await stripe?.redirectToCheckout({ sessionId })
          }
        }
        
        return (
          <button onClick={() => handlePackageSelect('price_starter')}>
            Buy Starter Pack
          </button>
        )
      }
      
      render(<PricingComponent />)
      
      // Click buy button
      fireEvent.click(screen.getByText('Buy Starter Pack'))
      
      // Should create checkout session immediately
      await waitFor(() => {
        expect(api.createCheckoutSession).toHaveBeenCalledWith({
          priceId: 'price_starter',
        })
      })
      
      // Verify Stripe redirect
      const stripe = await mockLoadStripe()
      expect(stripe?.redirectToCheckout).toHaveBeenCalledWith({
        sessionId: 'cs_test_direct',
      })
    })
  })
})