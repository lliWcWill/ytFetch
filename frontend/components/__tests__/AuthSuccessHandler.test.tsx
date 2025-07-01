import React from 'react'
import { render, waitFor } from '@testing-library/react'
import { useRouter, useSearchParams } from 'next/navigation'
import AuthSuccessHandler from '../AuthSuccessHandler'
import { loadStripe } from '@stripe/stripe-js'
import { api } from '@/services/api'

// Mock dependencies
jest.mock('next/navigation')
jest.mock('@stripe/stripe-js')
jest.mock('@/services/api')

describe('AuthSuccessHandler', () => {
  const mockUseRouter = useRouter as jest.MockedFunction<typeof useRouter>
  const mockUseSearchParams = useSearchParams as jest.MockedFunction<typeof useSearchParams>
  const mockLoadStripe = loadStripe as jest.MockedFunction<typeof loadStripe>
  
  let mockRouter: any
  let mockSearchParams: URLSearchParams

  beforeEach(() => {
    jest.clearAllMocks()
    console.log = jest.fn()
    console.error = jest.fn()
    
    // Setup router mock
    mockRouter = {
      push: jest.fn(),
      replace: jest.fn(),
      refresh: jest.fn(),
    }
    mockUseRouter.mockReturnValue(mockRouter)
    
    // Setup default search params
    mockSearchParams = new URLSearchParams()
    mockUseSearchParams.mockReturnValue(mockSearchParams)

    // Mock Stripe
    mockLoadStripe.mockResolvedValue({
      redirectToCheckout: jest.fn().mockResolvedValue({ error: null }),
    } as any)
  })

  describe('Auth Success Handling', () => {
    it('should clean up auth_success parameter', async () => {
      mockSearchParams = new URLSearchParams('auth_success=1&other_param=value')
      mockUseSearchParams.mockReturnValue(mockSearchParams)

      render(<AuthSuccessHandler />)

      await waitFor(() => {
        expect(mockRouter.replace).toHaveBeenCalledWith('/?other_param=value')
      })
    })

    it('should handle auth_success without other params', async () => {
      mockSearchParams = new URLSearchParams('auth_success=1')
      mockUseSearchParams.mockReturnValue(mockSearchParams)

      render(<AuthSuccessHandler />)

      await waitFor(() => {
        expect(mockRouter.replace).toHaveBeenCalledWith('/')
      })
    })

    it('should not do anything without auth_success param', async () => {
      mockSearchParams = new URLSearchParams('other_param=value')
      mockUseSearchParams.mockReturnValue(mockSearchParams)

      render(<AuthSuccessHandler />)

      // Wait a bit to ensure no replace is called
      await new Promise(resolve => setTimeout(resolve, 100))
      
      expect(mockRouter.replace).not.toHaveBeenCalled()
    })
  })

  describe('Auto-checkout Flow', () => {
    it('should trigger checkout when package param is present with auth_success', async () => {
      mockSearchParams = new URLSearchParams('auth_success=1&package=starter')
      mockUseSearchParams.mockReturnValue(mockSearchParams)

      ;(api.createCheckoutSession as jest.Mock).mockResolvedValue({
        sessionId: 'cs_test_123',
      })

      render(<AuthSuccessHandler />)

      // Should create checkout session
      await waitFor(() => {
        expect(api.createCheckoutSession).toHaveBeenCalledWith({
          priceId: 'price_1Qh0XgRw8qVPoloHIpOdnHtX', // Starter pack price ID
        })
      })

      // Should redirect to Stripe
      const stripe = await mockLoadStripe()
      expect(stripe?.redirectToCheckout).toHaveBeenCalledWith({
        sessionId: 'cs_test_123',
      })

      // Should clean up URL
      expect(mockRouter.replace).toHaveBeenCalledWith('/')
    })

    it('should handle different package types', async () => {
      const packages = [
        { param: 'starter', priceId: 'price_1Qh0XgRw8qVPoloHIpOdnHtX' },
        { param: 'popular', priceId: 'price_1Qh0YNRw8qVPoloHfQqYnAcT' },
        { param: 'volume', priceId: 'price_1Qh0ZARw8qVPoloHTQAzUXvH' },
      ]

      for (const pkg of packages) {
        jest.clearAllMocks()
        
        mockSearchParams = new URLSearchParams(`auth_success=1&package=${pkg.param}`)
        mockUseSearchParams.mockReturnValue(mockSearchParams)

        ;(api.createCheckoutSession as jest.Mock).mockResolvedValue({
          sessionId: `cs_test_${pkg.param}`,
        })

        const { unmount } = render(<AuthSuccessHandler />)

        await waitFor(() => {
          expect(api.createCheckoutSession).toHaveBeenCalledWith({
            priceId: pkg.priceId,
          })
        })

        unmount()
      }
    })

    it('should handle checkout errors gracefully', async () => {
      mockSearchParams = new URLSearchParams('auth_success=1&package=starter')
      mockUseSearchParams.mockReturnValue(mockSearchParams)

      const error = new Error('Checkout session creation failed')
      ;(api.createCheckoutSession as jest.Mock).mockRejectedValue(error)

      render(<AuthSuccessHandler />)

      await waitFor(() => {
        expect(console.error).toHaveBeenCalledWith('Checkout error:', error)
      })

      // Should still clean up URL even on error
      expect(mockRouter.replace).toHaveBeenCalledWith('/')
      
      // Should not attempt Stripe redirect
      expect(mockLoadStripe).not.toHaveBeenCalled()
    })

    it('should handle Stripe loading errors', async () => {
      mockSearchParams = new URLSearchParams('auth_success=1&package=starter')
      mockUseSearchParams.mockReturnValue(mockSearchParams)

      ;(api.createCheckoutSession as jest.Mock).mockResolvedValue({
        sessionId: 'cs_test_123',
      })

      mockLoadStripe.mockResolvedValue(null) // Stripe failed to load

      render(<AuthSuccessHandler />)

      await waitFor(() => {
        expect(console.error).toHaveBeenCalledWith(
          'Checkout error:',
          expect.any(Error)
        )
      })
    })

    it('should handle Stripe redirect errors', async () => {
      mockSearchParams = new URLSearchParams('auth_success=1&package=starter')
      mockUseSearchParams.mockReturnValue(mockSearchParams)

      ;(api.createCheckoutSession as jest.Mock).mockResolvedValue({
        sessionId: 'cs_test_123',
      })

      const stripeError = { type: 'card_error', message: 'Card declined' }
      mockLoadStripe.mockResolvedValue({
        redirectToCheckout: jest.fn().mockResolvedValue({ error: stripeError }),
      } as any)

      render(<AuthSuccessHandler />)

      await waitFor(() => {
        expect(console.error).toHaveBeenCalledWith(
          'Stripe redirect error:',
          stripeError
        )
      })
    })

    it('should not trigger checkout without auth_success', async () => {
      mockSearchParams = new URLSearchParams('package=starter')
      mockUseSearchParams.mockReturnValue(mockSearchParams)

      render(<AuthSuccessHandler />)

      // Wait to ensure no API calls are made
      await new Promise(resolve => setTimeout(resolve, 100))

      expect(api.createCheckoutSession).not.toHaveBeenCalled()
      expect(mockRouter.replace).not.toHaveBeenCalled()
    })

    it('should handle unknown package gracefully', async () => {
      mockSearchParams = new URLSearchParams('auth_success=1&package=unknown')
      mockUseSearchParams.mockReturnValue(mockSearchParams)

      render(<AuthSuccessHandler />)

      // Should still clean up URL but not attempt checkout
      await waitFor(() => {
        expect(mockRouter.replace).toHaveBeenCalledWith('/')
      })

      expect(api.createCheckoutSession).not.toHaveBeenCalled()
    })
  })

  describe('URL Parameter Preservation', () => {
    it('should preserve other parameters when cleaning up', async () => {
      mockSearchParams = new URLSearchParams('auth_success=1&tab=history&filter=recent')
      mockUseSearchParams.mockReturnValue(mockSearchParams)

      render(<AuthSuccessHandler />)

      await waitFor(() => {
        expect(mockRouter.replace).toHaveBeenCalledWith('/?tab=history&filter=recent')
      })
    })

    it('should handle complex query parameters', async () => {
      mockSearchParams = new URLSearchParams(
        'auth_success=1&package=starter&redirect=/dashboard&utm_source=email'
      )
      mockUseSearchParams.mockReturnValue(mockSearchParams)

      ;(api.createCheckoutSession as jest.Mock).mockResolvedValue({
        sessionId: 'cs_test_123',
      })

      render(<AuthSuccessHandler />)

      // Should process checkout
      await waitFor(() => {
        expect(api.createCheckoutSession).toHaveBeenCalled()
      })

      // Should preserve non-auth parameters
      expect(mockRouter.replace).toHaveBeenCalledWith('/?redirect=%2Fdashboard&utm_source=email')
    })
  })

  describe('Component Lifecycle', () => {
    it('should handle unmounting during async operations', async () => {
      mockSearchParams = new URLSearchParams('auth_success=1&package=starter')
      mockUseSearchParams.mockReturnValue(mockSearchParams)

      // Delay the API response
      ;(api.createCheckoutSession as jest.Mock).mockImplementation(
        () => new Promise(resolve => setTimeout(() => resolve({ sessionId: 'cs_test' }), 1000))
      )

      const { unmount } = render(<AuthSuccessHandler />)

      // Unmount before API completes
      unmount()

      // Wait to ensure no errors occur
      await new Promise(resolve => setTimeout(resolve, 1500))

      // Should not cause any errors
      expect(console.error).not.toHaveBeenCalledWith(
        expect.stringContaining("Can't perform a React state update")
      )
    })
  })
})