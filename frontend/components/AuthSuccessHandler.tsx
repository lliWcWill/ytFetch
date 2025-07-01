'use client'

import { useEffect } from 'react'
import { useSearchParams, useRouter } from 'next/navigation'
import { useAuth } from '@/providers/AuthProvider'

export function AuthSuccessHandler() {
  const searchParams = useSearchParams()
  const router = useRouter()
  const { refreshSession } = useAuth()

  useEffect(() => {
    // Check if we have the auth_success parameter
    if (searchParams.get('auth_success') === '1') {
      console.log('Auth success detected, refreshing auth state...')
      
      // Remove the auth_success parameter from URL
      const url = new URL(window.location.href)
      url.searchParams.delete('auth_success')
      
      // Replace the URL without the parameter
      window.history.replaceState({}, '', url.toString())
      
      // Refresh the session to ensure auth state is updated
      refreshSession().then(() => {
        console.log('Session refreshed successfully')
        // Trigger a router refresh to update all components
        router.refresh()
      }).catch((error) => {
        console.error('Failed to refresh session:', error)
        // Fallback to page reload if refresh fails
        window.location.reload()
      })
    }
  }, [searchParams, router, refreshSession])

  return null
}