import { NextResponse } from 'next/server'
import { GET } from '../route'
import { createClient } from '@/utils/supabase/server'

// Mock dependencies
jest.mock('next/server')
jest.mock('@/utils/supabase/server')

describe('Auth Callback Route', () => {
  let mockSupabaseClient: any
  let mockRequest: Request
  const origin = 'http://localhost:3000'

  beforeEach(() => {
    jest.clearAllMocks()
    console.error = jest.fn()
    console.log = jest.fn()

    // Setup mock Supabase client
    mockSupabaseClient = {
      auth: {
        exchangeCodeForSession: jest.fn(),
      },
    }
    
    ;(createClient as jest.Mock).mockResolvedValue(mockSupabaseClient)
    ;(NextResponse.redirect as jest.Mock).mockImplementation((url) => ({ url }))
  })

  describe('Successful Authentication', () => {
    it('should exchange code for session and redirect to home', async () => {
      mockRequest = new Request(`${origin}/auth/callback?code=test_code`)
      mockSupabaseClient.auth.exchangeCodeForSession.mockResolvedValue({ error: null })

      const response = await GET(mockRequest)

      expect(mockSupabaseClient.auth.exchangeCodeForSession).toHaveBeenCalledWith('test_code')
      expect(NextResponse.redirect).toHaveBeenCalledWith(`${origin}/?auth_success=1`)
    })

    it('should preserve intended destination through auth flow', async () => {
      const intendedPath = '/pricing?package=starter'
      mockRequest = new Request(`${origin}/auth/callback?code=test_code&next=${encodeURIComponent(intendedPath)}`)
      mockSupabaseClient.auth.exchangeCodeForSession.mockResolvedValue({ error: null })

      const response = await GET(mockRequest)

      expect(NextResponse.redirect).toHaveBeenCalledWith(
        `${origin}${intendedPath}&auth_success=1`
      )
    })

    it('should handle redirect_to parameter as fallback', async () => {
      const intendedPath = '/dashboard'
      mockRequest = new Request(`${origin}/auth/callback?code=test_code&redirect_to=${encodeURIComponent(intendedPath)}`)
      mockSupabaseClient.auth.exchangeCodeForSession.mockResolvedValue({ error: null })

      const response = await GET(mockRequest)

      expect(NextResponse.redirect).toHaveBeenCalledWith(
        `${origin}${intendedPath}?auth_success=1`
      )
    })

    it('should preserve query parameters in redirect', async () => {
      const intendedPath = '/billing?tab=history&filter=recent'
      mockRequest = new Request(`${origin}/auth/callback?code=test_code&next=${encodeURIComponent(intendedPath)}`)
      mockSupabaseClient.auth.exchangeCodeForSession.mockResolvedValue({ error: null })

      const response = await GET(mockRequest)

      expect(NextResponse.redirect).toHaveBeenCalledWith(
        `${origin}${intendedPath}&auth_success=1`
      )
    })
  })

  describe('Open Redirect Protection', () => {
    it('should not redirect to external URLs', async () => {
      const maliciousUrl = 'https://evil.com/phishing'
      mockRequest = new Request(`${origin}/auth/callback?code=test_code&next=${encodeURIComponent(maliciousUrl)}`)
      mockSupabaseClient.auth.exchangeCodeForSession.mockResolvedValue({ error: null })

      const response = await GET(mockRequest)

      // Should redirect to origin root, not the external URL
      expect(NextResponse.redirect).toHaveBeenCalledWith(`${origin}/?auth_success=1`)
      expect(NextResponse.redirect).not.toHaveBeenCalledWith(expect.stringContaining('evil.com'))
    })

    it('should handle protocol-relative URLs safely', async () => {
      const maliciousUrl = '//evil.com/phishing'
      mockRequest = new Request(`${origin}/auth/callback?code=test_code&next=${encodeURIComponent(maliciousUrl)}`)
      mockSupabaseClient.auth.exchangeCodeForSession.mockResolvedValue({ error: null })

      const response = await GET(mockRequest)

      expect(NextResponse.redirect).toHaveBeenCalledWith(`${origin}/?auth_success=1`)
      expect(NextResponse.redirect).not.toHaveBeenCalledWith(expect.stringContaining('evil.com'))
    })
  })

  describe('Error Handling', () => {
    it('should handle OAuth provider errors', async () => {
      mockRequest = new Request(`${origin}/auth/callback?error=access_denied&error_description=User%20denied%20access`)

      const response = await GET(mockRequest)

      expect(console.error).toHaveBeenCalledWith('OAuth error:', 'access_denied', 'User denied access')
      expect(NextResponse.redirect).toHaveBeenCalledWith(
        `${origin}/auth/auth-code-error?error=access_denied`
      )
    })

    it('should handle code exchange errors', async () => {
      mockRequest = new Request(`${origin}/auth/callback?code=invalid_code`)
      mockSupabaseClient.auth.exchangeCodeForSession.mockResolvedValue({ 
        error: { message: 'Invalid authorization code' } 
      })

      const response = await GET(mockRequest)

      expect(console.error).toHaveBeenCalledWith(
        'Code exchange error:', 
        expect.objectContaining({ message: 'Invalid authorization code' })
      )
      expect(NextResponse.redirect).toHaveBeenCalledWith(
        `${origin}/auth/auth-code-error?error=exchange_failed`
      )
    })

    it('should handle unexpected errors', async () => {
      mockRequest = new Request(`${origin}/auth/callback?code=test_code`)
      mockSupabaseClient.auth.exchangeCodeForSession.mockRejectedValue(
        new Error('Network error')
      )

      const response = await GET(mockRequest)

      expect(console.error).toHaveBeenCalledWith(
        'Unexpected error during auth:', 
        expect.any(Error)
      )
      expect(NextResponse.redirect).toHaveBeenCalledWith(
        `${origin}/auth/auth-code-error?error=unexpected`
      )
    })

    it('should handle missing code parameter', async () => {
      mockRequest = new Request(`${origin}/auth/callback`)

      const response = await GET(mockRequest)

      expect(NextResponse.redirect).toHaveBeenCalledWith(
        `${origin}/auth/auth-code-error?error=no_code`
      )
    })
  })

  describe('Logging', () => {
    it('should log successful redirects for debugging', async () => {
      const intendedPath = '/pricing'
      mockRequest = new Request(`${origin}/auth/callback?code=test_code&next=${intendedPath}`)
      mockSupabaseClient.auth.exchangeCodeForSession.mockResolvedValue({ error: null })

      await GET(mockRequest)

      expect(console.log).toHaveBeenCalledWith('Auth callback redirect:', {
        next: intendedPath,
        redirectUrl: `${origin}${intendedPath}`,
      })
    })
  })
})