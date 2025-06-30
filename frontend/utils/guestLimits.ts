/**
 * Guest user limits tracking
 * Uses localStorage to track usage for non-authenticated users
 */

export interface GuestUsage {
  transcriptions: number
  bulkJobs: number
  lastReset: string
  createdAt: string
}

const GUEST_STORAGE_KEY = 'ytfetch_guest_usage'

// Guest tier limits
export const GUEST_LIMITS = {
  transcriptions: 5,   // 5 free transcriptions per day
  bulkJobs: 1,        // 1 free bulk job per day
  maxBulkVideos: 10,  // Max 10 videos in bulk job
}

export function getGuestUsage(): GuestUsage {
  if (typeof window === 'undefined') {
    return createDefaultUsage()
  }

  const stored = localStorage.getItem(GUEST_STORAGE_KEY)
  if (!stored) {
    const newUsage = createDefaultUsage()
    localStorage.setItem(GUEST_STORAGE_KEY, JSON.stringify(newUsage))
    return newUsage
  }

  try {
    const usage = JSON.parse(stored) as GuestUsage
    
    // Check if we need to reset daily limits
    const lastReset = new Date(usage.lastReset)
    const now = new Date()
    const daysSinceReset = Math.floor((now.getTime() - lastReset.getTime()) / (1000 * 60 * 60 * 24))
    
    if (daysSinceReset >= 1) {
      // Reset daily limits
      usage.transcriptions = 0
      usage.bulkJobs = 0
      usage.lastReset = now.toISOString()
      localStorage.setItem(GUEST_STORAGE_KEY, JSON.stringify(usage))
    }
    
    return usage
  } catch {
    // If corrupted, create new
    const newUsage = createDefaultUsage()
    localStorage.setItem(GUEST_STORAGE_KEY, JSON.stringify(newUsage))
    return newUsage
  }
}

function createDefaultUsage(): GuestUsage {
  const now = new Date().toISOString()
  return {
    transcriptions: 0,
    bulkJobs: 0,
    lastReset: now,
    createdAt: now,
  }
}

export function incrementGuestUsage(type: 'transcriptions' | 'bulkJobs'): boolean {
  const usage = getGuestUsage()
  
  // Check if limit reached
  if (usage[type] >= GUEST_LIMITS[type]) {
    return false // Limit reached
  }
  
  // Increment usage
  usage[type]++
  localStorage.setItem(GUEST_STORAGE_KEY, JSON.stringify(usage))
  return true
}

export function checkGuestLimit(type: 'transcriptions' | 'bulkJobs'): {
  allowed: boolean
  current: number
  limit: number
  remaining: number
} {
  const usage = getGuestUsage()
  const limit = GUEST_LIMITS[type]
  const current = usage[type]
  const remaining = Math.max(0, limit - current)
  
  return {
    allowed: current < limit,
    current,
    limit,
    remaining,
  }
}

export function getRemainingGuestUsage() {
  const usage = getGuestUsage()
  return {
    transcriptions: Math.max(0, GUEST_LIMITS.transcriptions - usage.transcriptions),
    bulkJobs: Math.max(0, GUEST_LIMITS.bulkJobs - usage.bulkJobs),
  }
}