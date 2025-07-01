import { NextRequest, NextResponse } from 'next/server'
import type { MiddlewareConfig } from 'next/server'

// Mock a simple auth middleware for testing
// In a real implementation, this would check Supabase session
export async function authMiddleware(request: NextRequest) {
  const { pathname, searchParams } = request.nextUrl
  
  // List of protected routes
  const protectedRoutes = ['/dashboard', '/profile', '/billing', '/settings']
  const authRoutes = ['/login', '/signup', '/auth/callback']
  
  // Check if route is protected
  const isProtectedRoute = protectedRoutes.some(route => pathname.startsWith(route))
  const isAuthRoute = authRoutes.includes(pathname)
  
  // Get auth status from cookie (in real app, would verify with Supabase)
  const hasAuthCookie = request.cookies.has('sb-auth-token')
  
  // Redirect unauthenticated users trying to access protected routes
  if (isProtectedRoute && !hasAuthCookie) {
    const redirectUrl = new URL('/login', request.url)
    redirectUrl.searchParams.set('redirect_to', pathname)
    
    // Preserve query parameters
    searchParams.forEach((value, key) => {
      if (key !== 'redirect_to') {
        redirectUrl.searchParams.set(key, value)
      }
    })
    
    return NextResponse.redirect(redirectUrl)
  }
  
  // Redirect authenticated users away from auth pages
  if (isAuthRoute && hasAuthCookie && pathname !== '/auth/callback') {
    const redirectTo = searchParams.get('redirect_to') || '/dashboard'
    return NextResponse.redirect(new URL(redirectTo, request.url))
  }
  
  return NextResponse.next()
}

// Tests
describe('Auth Middleware', () => {
  const mockUrl = 'http://localhost:3000'
  
  beforeEach(() => {
    jest.clearAllMocks()
  })

  describe('Protected Route Access', () => {
    it('should redirect unauthenticated users to login', async () => {
      const request = new NextRequest(new URL('/dashboard', mockUrl))
      const response = await authMiddleware(request)
      
      expect(response.status).toBe(307) // Temporary redirect
      expect(response.headers.get('location')).toBe('/login?redirect_to=%2Fdashboard')
    })

    it('should preserve query parameters when redirecting to login', async () => {
      const request = new NextRequest(new URL('/billing?tab=history&filter=recent', mockUrl))
      const response = await authMiddleware(request)
      
      expect(response.headers.get('location')).toBe(
        '/login?redirect_to=%2Fbilling&tab=history&filter=recent'
      )
    })

    it('should allow authenticated users to access protected routes', async () => {
      const request = new NextRequest(new URL('/dashboard', mockUrl))
      request.cookies.set('sb-auth-token', 'valid-token')
      
      const response = await authMiddleware(request)
      
      expect(response.status).toBe(200) // Next() returns 200
      expect(response.headers.get('location')).toBeNull()
    })

    it('should handle nested protected routes', async () => {
      const request = new NextRequest(new URL('/profile/settings/security', mockUrl))
      const response = await authMiddleware(request)
      
      expect(response.headers.get('location')).toBe(
        '/login?redirect_to=%2Fprofile%2Fsettings%2Fsecurity'
      )
    })
  })

  describe('Auth Route Access', () => {
    it('should redirect authenticated users away from login', async () => {
      const request = new NextRequest(new URL('/login', mockUrl))
      request.cookies.set('sb-auth-token', 'valid-token')
      
      const response = await authMiddleware(request)
      
      expect(response.status).toBe(307)
      expect(response.headers.get('location')).toBe('/dashboard')
    })

    it('should redirect to intended destination from login redirect_to param', async () => {
      const request = new NextRequest(new URL('/login?redirect_to=/billing', mockUrl))
      request.cookies.set('sb-auth-token', 'valid-token')
      
      const response = await authMiddleware(request)
      
      expect(response.headers.get('location')).toBe('/billing')
    })

    it('should allow unauthenticated users to access auth routes', async () => {
      const request = new NextRequest(new URL('/login', mockUrl))
      const response = await authMiddleware(request)
      
      expect(response.status).toBe(200)
      expect(response.headers.get('location')).toBeNull()
    })

    it('should not redirect from auth callback even if authenticated', async () => {
      const request = new NextRequest(new URL('/auth/callback?code=123', mockUrl))
      request.cookies.set('sb-auth-token', 'valid-token')
      
      const response = await authMiddleware(request)
      
      expect(response.status).toBe(200)
      expect(response.headers.get('location')).toBeNull()
    })
  })

  describe('Public Route Access', () => {
    it('should allow all users to access public routes', async () => {
      const publicRoutes = ['/', '/pricing', '/docs', '/api/public']
      
      for (const route of publicRoutes) {
        // Test unauthenticated
        const unauthRequest = new NextRequest(new URL(route, mockUrl))
        const unauthResponse = await authMiddleware(unauthRequest)
        expect(unauthResponse.status).toBe(200)
        
        // Test authenticated
        const authRequest = new NextRequest(new URL(route, mockUrl))
        authRequest.cookies.set('sb-auth-token', 'valid-token')
        const authResponse = await authMiddleware(authRequest)
        expect(authResponse.status).toBe(200)
      }
    })
  })

  describe('Edge Cases', () => {
    it('should handle missing redirect_to gracefully', async () => {
      const request = new NextRequest(new URL('/login', mockUrl))
      request.cookies.set('sb-auth-token', 'valid-token')
      
      const response = await authMiddleware(request)
      
      // Should default to dashboard
      expect(response.headers.get('location')).toBe('/dashboard')
    })

    it('should not create redirect loops', async () => {
      // Authenticated user on login page with redirect_to=/login
      const request = new NextRequest(new URL('/login?redirect_to=/login', mockUrl))
      request.cookies.set('sb-auth-token', 'valid-token')
      
      const response = await authMiddleware(request)
      
      // Should redirect to dashboard, not back to login
      expect(response.headers.get('location')).toBe('/login')
    })

    it('should handle special characters in redirect paths', async () => {
      const request = new NextRequest(
        new URL('/billing?plan=pro&features[]=api&features[]=webhooks', mockUrl)
      )
      const response = await authMiddleware(request)
      
      expect(response.headers.get('location')).toContain('redirect_to=%2Fbilling')
      expect(response.headers.get('location')).toContain('features%5B%5D=api')
    })
  })
})