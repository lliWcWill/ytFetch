export interface TokenPackage {
  id: string
  name: string
  displayName: string
  tokens: number
  price: number
  priceDisplay: string
  description: string
  popular?: boolean
  savings?: string
  perTokenPrice: number
}

export interface TokenTransaction {
  id: string
  userId: string
  amount: number
  type: 'purchase' | 'usage' | 'refund' | 'bonus'
  description: string
  createdAt: string
  metadata?: {
    packageId?: string
    jobId?: string
    videoCount?: number
  }
}

export interface UserTokenBalance {
  userId: string
  balance: number
  lifetimeSpent: number
  lifetimePurchased: number
  lastPurchaseAt?: string
  createdAt: string
  updatedAt: string
}

export interface TokenUsageRate {
  singleVideo: number
  playlistVideo: number
  channelVideo: number
}

export const TOKEN_PACKAGES: TokenPackage[] = [
  {
    id: 'starter',
    name: 'starter',
    displayName: 'Starter Pack',
    tokens: 50,
    price: 2.99,
    priceDisplay: '$2.99',
    description: 'Perfect for trying out ytFetch',
    perTokenPrice: 0.0598
  },
  {
    id: 'popular',
    name: 'popular',
    displayName: 'Popular Pack',
    tokens: 150,
    price: 6.99,
    priceDisplay: '$6.99',
    description: 'Most popular choice for regular users',
    popular: true,
    savings: 'Save 22%',
    perTokenPrice: 0.0466
  },
  {
    id: 'volume',
    name: 'volume',
    displayName: 'High Volume',
    tokens: 500,
    price: 17.99,
    priceDisplay: '$17.99',
    description: 'Best value for power users',
    savings: 'Save 40%',
    perTokenPrice: 0.0360
  }
]

export const TOKEN_USAGE_RATES: TokenUsageRate = {
  singleVideo: 1,
  playlistVideo: 1,
  channelVideo: 1
}