'use client'

import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { useRouter } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { 
  Coins, 
  TrendingUp, 
  CreditCard, 
  History,
  ShoppingBag,
  ArrowUpRight,
  ArrowDownRight,
  Package,
  Zap,
  RefreshCw
} from 'lucide-react'
import { useAuth } from '@/providers/AuthProvider'
import { tokenService } from '@/services/tokenService'
import { TokenTransaction, UserTokenBalance } from '@/types/tokens'
import { cn } from '@/lib/utils'

export default function DashboardPage() {
  const { user, loading: authLoading } = useAuth()
  const router = useRouter()
  
  const [balance, setBalance] = useState<UserTokenBalance | null>(null)
  const [transactions, setTransactions] = useState<TokenTransaction[]>([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!authLoading && !user) {
      sessionStorage.setItem('auth-redirect-to', '/dashboard')
      router.push('/login')
    }
  }, [user, authLoading, router])

  const loadData = async () => {
    if (!user) return
    
    try {
      setError(null)
      const [balanceData, transactionData] = await Promise.all([
        tokenService.getTokenBalance(),
        tokenService.getTransactionHistory()
      ])
      
      setBalance(balanceData)
      setTransactions(transactionData.transactions)
    } catch (err) {
      console.error('Failed to load dashboard data:', err)
      setError('Failed to load dashboard data. Please try again.')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }

  useEffect(() => {
    if (user) {
      loadData()
    }
  }, [user])

  const handleRefresh = async () => {
    setRefreshing(true)
    await loadData()
  }

  if (authLoading || loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-zinc-950">
        <div className="flex flex-col items-center space-y-4">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-orange-500"></div>
          <p className="text-sm text-zinc-500">Loading dashboard...</p>
        </div>
      </div>
    )
  }

  if (!user) {
    return null
  }

  const getTransactionIcon = (type: TokenTransaction['type']) => {
    switch (type) {
      case 'purchase':
        return <ArrowDownRight className="h-4 w-4 text-green-500" />
      case 'usage':
        return <ArrowUpRight className="h-4 w-4 text-orange-500" />
      case 'refund':
        return <RefreshCw className="h-4 w-4 text-blue-500" />
      case 'bonus':
        return <Zap className="h-4 w-4 text-purple-500" />
    }
  }

  const getTransactionColor = (type: TokenTransaction['type']) => {
    switch (type) {
      case 'purchase':
        return 'text-green-600'
      case 'usage':
        return 'text-orange-600'
      case 'refund':
        return 'text-blue-600'
      case 'bonus':
        return 'text-purple-600'
    }
  }

  const formatDate = (dateString: string) => {
    const date = new Date(dateString)
    const now = new Date()
    const diffInHours = (now.getTime() - date.getTime()) / (1000 * 60 * 60)
    
    if (diffInHours < 24) {
      if (diffInHours < 1) {
        const diffInMinutes = Math.floor(diffInHours * 60)
        return `${diffInMinutes} minute${diffInMinutes !== 1 ? 's' : ''} ago`
      }
      const hours = Math.floor(diffInHours)
      return `${hours} hour${hours !== 1 ? 's' : ''} ago`
    } else if (diffInHours < 168) { // 7 days
      const days = Math.floor(diffInHours / 24)
      return `${days} day${days !== 1 ? 's' : ''} ago`
    }
    
    return date.toLocaleDateString('en-US', { 
      month: 'short', 
      day: 'numeric',
      year: date.getFullYear() !== now.getFullYear() ? 'numeric' : undefined
    })
  }

  return (
    <div className="min-h-screen bg-zinc-950">
      <div className="container mx-auto px-4 py-8">
        <div className="max-w-7xl mx-auto space-y-8">
          {/* Header */}
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-4xl font-bold text-zinc-100">Token Dashboard</h1>
              <p className="text-zinc-400 mt-2">
                Manage your tokens and view transaction history
              </p>
            </div>
            <div className="flex items-center gap-4">
              <Button
                variant="outline"
                size="sm"
                onClick={handleRefresh}
                disabled={refreshing}
              >
                <RefreshCw className={cn("h-4 w-4 mr-2", refreshing && "animate-spin")} />
                Refresh
              </Button>
              <Button
                onClick={() => router.push('/pricing')}
                className="bg-gradient-to-r from-orange-500 to-orange-600 hover:from-orange-600 hover:to-orange-700 shadow-lg shadow-orange-500/20"
              >
                <ShoppingBag className="h-4 w-4 mr-2" />
                Buy Tokens
              </Button>
            </div>
          </div>

          {error && (
            <div className="p-4 bg-red-500/10 text-red-500 border border-red-500/20 rounded-lg">
              {error}
            </div>
          )}

          {/* Stats Cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {/* Current Balance */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 }}
            >
              <Card className="relative overflow-hidden bg-zinc-900 border-zinc-800">
                <div className="absolute inset-0 bg-gradient-to-br from-orange-500/10 to-orange-600/10" />
                <CardHeader className="relative">
                  <CardTitle className="flex items-center justify-between">
                    <span>Current Balance</span>
                    <Coins className="h-5 w-5 text-orange-500" />
                  </CardTitle>
                </CardHeader>
                <CardContent className="relative">
                  <div className="text-3xl font-bold text-zinc-100">
                    {balance ? tokenService.formatTokens(balance.balance) : '0'}
                  </div>
                  <p className="text-sm text-zinc-500 mt-1">tokens available</p>
                </CardContent>
              </Card>
            </motion.div>

            {/* Lifetime Purchased */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 }}
            >
              <Card className="bg-zinc-900 border-zinc-800">
                <CardHeader>
                  <CardTitle className="flex items-center justify-between">
                    <span>Total Purchased</span>
                    <CreditCard className="h-5 w-5 text-green-500" />
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-3xl font-bold text-zinc-100">
                    {balance ? tokenService.formatTokens(balance.lifetimePurchased) : '0'}
                  </div>
                  <p className="text-sm text-zinc-500 mt-1">lifetime tokens</p>
                </CardContent>
              </Card>
            </motion.div>

            {/* Lifetime Used */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3 }}
            >
              <Card className="bg-zinc-900 border-zinc-800">
                <CardHeader>
                  <CardTitle className="flex items-center justify-between">
                    <span>Total Used</span>
                    <TrendingUp className="h-5 w-5 text-blue-500" />
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-3xl font-bold text-zinc-100">
                    {balance ? tokenService.formatTokens(balance.lifetimeSpent) : '0'}
                  </div>
                  <p className="text-sm text-zinc-500 mt-1">videos transcribed</p>
                </CardContent>
              </Card>
            </motion.div>
          </div>

          {/* Transaction History */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4 }}
          >
            <Card className="bg-zinc-900 border-zinc-800">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-zinc-100">
                  <History className="h-5 w-5" />
                  Transaction History
                </CardTitle>
                <CardDescription className="text-zinc-500">
                  Your recent token transactions
                </CardDescription>
              </CardHeader>
              <CardContent>
                {transactions.length === 0 ? (
                  <div className="text-center py-12">
                    <Package className="h-12 w-12 text-zinc-600 mx-auto mb-4" />
                    <p className="text-zinc-500">No transactions yet</p>
                    <Button
                      onClick={() => router.push('/pricing')}
                      className="mt-4"
                      variant="outline"
                    >
                      Buy your first tokens
                    </Button>
                  </div>
                ) : (
                  <div className="space-y-4">
                    {transactions.map((transaction) => (
                      <div
                        key={transaction.id}
                        className="flex items-center justify-between p-4 rounded-lg border border-zinc-800 bg-zinc-800/50 hover:bg-zinc-800 transition-colors"
                      >
                        <div className="flex items-center gap-4">
                          <div className="w-10 h-10 rounded-full bg-zinc-800 flex items-center justify-center">
                            {getTransactionIcon(transaction.type)}
                          </div>
                          <div>
                            <p className="font-medium text-zinc-100">{transaction.description}</p>
                            <p className="text-sm text-zinc-500">
                              {formatDate(transaction.createdAt)}
                            </p>
                          </div>
                        </div>
                        <div className="text-right">
                          <p className={cn("font-semibold text-lg", getTransactionColor(transaction.type))}>
                            {transaction.type === 'usage' ? '-' : '+'}
                            {tokenService.formatTokens(Math.abs(transaction.amount))}
                          </p>
                          <p className="text-sm text-zinc-500">tokens</p>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </motion.div>

          {/* Quick Actions */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <Card className="bg-gradient-to-br from-orange-500/10 to-orange-600/10 border-orange-500/20">
              <CardHeader>
                <CardTitle className="text-zinc-100">Need more tokens?</CardTitle>
                <CardDescription className="text-zinc-400">
                  Purchase token packages to continue transcribing
                </CardDescription>
              </CardHeader>
              <CardContent>
                <Button 
                  onClick={() => router.push('/pricing')}
                  className="w-full bg-gradient-to-r from-orange-500 to-orange-600 hover:from-orange-600 hover:to-orange-700 shadow-lg shadow-orange-500/20"
                >
                  View Token Packages
                </Button>
              </CardContent>
            </Card>

            <Card className="bg-gradient-to-br from-blue-500/10 to-purple-500/10 border-blue-500/20">
              <CardHeader>
                <CardTitle className="text-zinc-100">Ready to transcribe?</CardTitle>
                <CardDescription className="text-zinc-400">
                  Start transcribing videos with your tokens
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex gap-2">
                  <Button 
                    onClick={() => router.push('/')}
                    variant="outline"
                    className="flex-1 border-zinc-800 hover:bg-zinc-900 text-zinc-300 hover:text-zinc-100"
                  >
                    Single Video
                  </Button>
                  <Button 
                    onClick={() => router.push('/bulk')}
                    variant="outline"
                    className="flex-1 border-zinc-800 hover:bg-zinc-900 text-zinc-300 hover:text-zinc-100"
                  >
                    Bulk Process
                  </Button>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </div>
  )
}