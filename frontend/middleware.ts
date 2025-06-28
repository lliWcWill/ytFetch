import { NextResponse, type NextRequest } from 'next/server'

export async function middleware(request: NextRequest) {
  try {
    const response = NextResponse.next()

    // For now, we'll handle auth protection on the client side
    // This middleware can be enhanced later when we add the auth-helpers package
    
    // Protected routes that require authentication
    const protectedPaths = ['/profile', '/settings', '/billing']
    const isProtectedPath = protectedPaths.some(path => 
      request.nextUrl.pathname.startsWith(path)
    )

    // For protected paths, we'll let the client-side auth handle the redirect
    // This is a simplified approach that works with our current setup
    if (isProtectedPath) {
      // Add a header to indicate this is a protected route
      response.headers.set('x-auth-required', 'true')
    }

    return response
  } catch (e) {
    // If there's an error, just continue
    console.error('Middleware error:', e)
    return NextResponse.next()
  }
}

export const config = {
  matcher: [
    /*
     * Match all request paths except for the ones starting with:
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico (favicon file)
     * - public folder
     */
    '/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)',
  ],
}