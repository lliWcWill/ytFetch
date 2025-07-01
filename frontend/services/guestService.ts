/**
 * Guest Service for ytFetch Frontend
 * Handles guest usage tracking and limit display
 */

import { getApiUrl } from './api'
import { createAuthHeaders } from '@/lib/auth-token'

export interface GuestUsage {
  unofficial: {
    used: number
    limit: number
    remaining: number
  }
  groq: {
    used: number
    limit: number
    remaining: number
  }
  bulk: {
    used: number
    limit: number
    remaining: number
  }
}

export interface GuestUsageResponse {
  is_guest: boolean
  session_id?: string
  usage: GuestUsage
  first_use_at?: string
  last_use_at?: string
  message?: string
  // For authenticated users
  user_id?: string
  email?: string
  tier?: string
  limits?: any
  subscription?: any
}

export interface GuestLimitError {
  error_code: 'guest_limit_exceeded'
  message: string
  usage: {
    current_usage: number
    limit: number
    remaining: number
  }
  requires_auth: boolean
}

/**
 * Gets the current usage for the user (guest or authenticated)
 */
export async function getUsage(): Promise<GuestUsageResponse> {
  const apiUrl = getApiUrl()
  const headers = await createAuthHeaders()

  try {
    console.log('Fetching guest usage from:', `${apiUrl}/api/v1/guest/usage`); // Debug log
    const response = await fetch(`${apiUrl}/api/v1/guest/usage`, {
      method: 'GET',
      headers,
    })

    if (!response.ok) {
      throw new Error(`Failed to get usage: ${response.statusText}`)
    }

    return await response.json()
  } catch (error) {
    console.error('Error getting usage:', error)
    console.error('API URL was:', apiUrl) // Debug log
    // Return default guest usage on error
    return {
      is_guest: true,
      usage: {
        unofficial: { used: 0, limit: 10, remaining: 10 },
        groq: { used: 0, limit: 10, remaining: 10 },
        bulk: { used: 0, limit: 50, remaining: 50 }
      }
    }
  }
}

/**
 * Checks if a guest has remaining usage for a specific method
 */
export function hasRemainingUsage(usage: GuestUsage, method: 'unofficial' | 'groq'): boolean {
  return usage[method].remaining > 0
}

/**
 * Gets a user-friendly message about remaining usage
 */
export function getUsageMessage(usage: GuestUsage, method: 'unofficial' | 'groq'): string {
  const methodUsage = usage[method]
  
  if (methodUsage.remaining === 0) {
    return `You've used all ${methodUsage.limit} free ${method} transcriptions. Sign up for unlimited access!`
  }
  
  if (methodUsage.remaining <= 3) {
    return `Only ${methodUsage.remaining} free ${method} transcription${methodUsage.remaining === 1 ? '' : 's'} left!`
  }
  
  return `${methodUsage.remaining} of ${methodUsage.limit} free transcriptions remaining`
}

/**
 * Checks if the error is a guest limit error
 */
export function isGuestLimitError(error: any): error is GuestLimitError {
  return error?.error_code === 'guest_limit_exceeded'
}

/**
 * Gets the usage type display name
 */
export function getUsageTypeDisplayName(type: 'unofficial' | 'groq' | 'bulk'): string {
  switch (type) {
    case 'unofficial':
      return 'YouTube subtitles'
    case 'groq':
      return 'AI transcriptions'
    case 'bulk':
      return 'bulk downloads'
    default:
      return type
  }
}