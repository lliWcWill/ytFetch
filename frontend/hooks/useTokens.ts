'use client'

import { useState, useEffect, useCallback } from 'react'
import { useAuth } from '@/providers/AuthProvider'
import { tokenService } from '@/services/tokenService'
import { UserTokenBalance } from '@/types/tokens'

export function useTokens() {
  const { user } = useAuth()
  const [balance, setBalance] = useState<UserTokenBalance | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadBalance = useCallback(async () => {
    if (!user) {
      setBalance(null)
      setLoading(false)
      return
    }

    try {
      setError(null)
      const data = await tokenService.getTokenBalance()
      setBalance(data)
    } catch (err) {
      console.error('Failed to load token balance:', err)
      setError('Failed to load token balance')
    } finally {
      setLoading(false)
    }
  }, [user])

  useEffect(() => {
    loadBalance()
  }, [loadBalance])

  const checkBalance = useCallback(async (requiredTokens: number) => {
    if (!user) return { hasEnough: false, balance: 0, required: requiredTokens }
    
    try {
      return await tokenService.checkTokens(requiredTokens)
    } catch (err) {
      console.error('Failed to check tokens:', err)
      return { hasEnough: false, balance: 0, required: requiredTokens }
    }
  }, [user])

  const useTokens = useCallback(async (jobId: string, videoCount: number = 1) => {
    if (!user) throw new Error('Authentication required')
    
    try {
      const result = await tokenService.useTokens(jobId, videoCount)
      // Reload balance after using tokens
      await loadBalance()
      return result
    } catch (err) {
      console.error('Failed to use tokens:', err)
      throw err
    }
  }, [user, loadBalance])

  const purchaseTokens = useCallback(async (packageId: string) => {
    if (!user) throw new Error('Authentication required')
    
    try {
      return await tokenService.purchaseTokens(packageId)
    } catch (err) {
      console.error('Failed to purchase tokens:', err)
      throw err
    }
  }, [user])

  return {
    balance,
    loading,
    error,
    loadBalance,
    checkBalance,
    useTokens,
    purchaseTokens,
    isAuthenticated: !!user
  }
}