import { TOKEN_PACKAGES, TokenPackage, TokenTransaction, UserTokenBalance } from '@/types/tokens'
import { ApiValidationError, ApiNetworkError, ApiHttpError } from './api'
import { getAuthToken } from '@/lib/auth-token'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

class TokenService {
  // Get user's token balance
  async getTokenBalance(): Promise<UserTokenBalance> {
    const token = await getAuthToken()
    
    if (!token) {
      throw new ApiValidationError('Authentication required')
    }

    try {
      const response = await fetch(`${API_URL}/api/tokens/balance`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      })

      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Failed to get token balance' }))
        throw new ApiHttpError(error.detail || 'Failed to get token balance', response.status)
      }

      return await response.json()
    } catch (error) {
      if (error instanceof ApiHttpError) throw error
      throw new ApiNetworkError('Failed to connect to server')
    }
  }

  // Get transaction history
  async getTransactionHistory(limit: number = 50, offset: number = 0): Promise<{
    transactions: TokenTransaction[]
    total: number
  }> {
    const token = await getAuthToken()
    
    if (!token) {
      throw new ApiValidationError('Authentication required')
    }

    try {
      const response = await fetch(
        `${API_URL}/api/tokens/transactions?limit=${limit}&offset=${offset}`,
        {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          }
        }
      )

      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Failed to get transactions' }))
        throw new ApiHttpError(error.detail || 'Failed to get transactions', response.status)
      }

      return await response.json()
    } catch (error) {
      if (error instanceof ApiHttpError) throw error
      throw new ApiNetworkError('Failed to connect to server')
    }
  }

  // Purchase tokens
  async purchaseTokens(packageId: string): Promise<{ checkoutUrl: string }> {
    const token = await getAuthToken()
    
    if (!token) {
      throw new ApiValidationError('Authentication required')
    }

    const tokenPackage = TOKEN_PACKAGES.find(pkg => pkg.id === packageId)
    if (!tokenPackage) {
      throw new ApiValidationError('Invalid token package')
    }

    try {
      const response = await fetch(`${API_URL}/api/tokens/purchase`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          package_id: packageId,
          tokens: tokenPackage.tokens,
          price: tokenPackage.price
        })
      })

      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Failed to create checkout' }))
        throw new ApiHttpError(error.detail || 'Failed to create checkout', response.status)
      }

      const data = await response.json()
      
      // Redirect to Stripe Checkout
      if (data.checkout_url) {
        window.location.href = data.checkout_url
      }
      
      return data
    } catch (error) {
      if (error instanceof ApiHttpError) throw error
      throw new ApiNetworkError('Failed to connect to server')
    }
  }

  // Use tokens for a transcription
  async useTokens(jobId: string, videoCount: number = 1): Promise<{
    success: boolean
    remainingBalance: number
  }> {
    const token = await getAuthToken()
    
    if (!token) {
      throw new ApiValidationError('Authentication required')
    }

    try {
      const response = await fetch(`${API_URL}/api/tokens/use`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          job_id: jobId,
          video_count: videoCount,
          amount: videoCount // 1 token per video
        })
      })

      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Failed to use tokens' }))
        throw new ApiHttpError(error.detail || 'Failed to use tokens', response.status)
      }

      return await response.json()
    } catch (error) {
      if (error instanceof ApiHttpError) throw error
      throw new ApiNetworkError('Failed to connect to server')
    }
  }

  // Check if user has enough tokens
  async checkTokens(requiredTokens: number): Promise<{
    hasEnough: boolean
    balance: number
    required: number
  }> {
    try {
      const balance = await this.getTokenBalance()
      return {
        hasEnough: balance.balance >= requiredTokens,
        balance: balance.balance,
        required: requiredTokens
      }
    } catch (error) {
      console.error('Failed to check tokens:', error)
      return {
        hasEnough: false,
        balance: 0,
        required: requiredTokens
      }
    }
  }

  // Format token amount with proper display
  formatTokens(amount: number): string {
    return new Intl.NumberFormat('en-US').format(amount)
  }

  // Get estimated token cost for videos
  getEstimatedCost(videoCount: number, type: 'single' | 'playlist' | 'channel' = 'single'): number {
    // For now, all video types cost 1 token each
    return videoCount
  }
}

export const tokenService = new TokenService()