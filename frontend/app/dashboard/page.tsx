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
  RefreshCw,
  FileText,
  Clock,
  CheckCircle,
  XCircle,
  AlertCircle,
  Loader2,
  PlayCircle,
  ListVideo
} from 'lucide-react'
import { useAuth } from '@/providers/AuthProvider'
import { tokenService } from '@/services/tokenService'
import { TokenTransaction, UserTokenBalance } from '@/types/tokens'
import { cn } from '@/lib/utils'

// Demo data for when there's no real data
const generateDemoTransactions = (): TokenTransaction[] => {
  const now = new Date()
  const transactions: TokenTransaction[] = [
    {
      id: 'demo-1',
      userId: 'demo',
      amount: 150,
      type: 'purchase',
      description: 'Popular Pack - 150 tokens',
      createdAt: new Date(now.getTime() - 2 * 60 * 60 * 1000).toISOString(), // 2 hours ago
      metadata: { packageId: 'popular' }
    },
    {
      id: 'demo-2',
      userId: 'demo',
      amount: -12,
      type: 'usage',
      description: 'Transcribed 12 videos from "Tech Reviews 2024" playlist',
      createdAt: new Date(now.getTime() - 6 * 60 * 60 * 1000).toISOString(), // 6 hours ago
      metadata: { jobId: 'job-001', videoCount: 12 }
    },
    {
      id: 'demo-3',
      userId: 'demo',
      amount: -3,
      type: 'usage',
      description: 'Single video transcription - "How to Build a SaaS"',
      createdAt: new Date(now.getTime() - 24 * 60 * 60 * 1000).toISOString(), // 1 day ago
    },
    {
      id: 'demo-4',
      userId: 'demo',
      amount: 50,
      type: 'bonus',
      description: 'Welcome bonus for new users',
      createdAt: new Date(now.getTime() - 2 * 24 * 60 * 60 * 1000).toISOString(), // 2 days ago
    },
    {
      id: 'demo-5',
      userId: 'demo',
      amount: -25,
      type: 'usage',
      description: 'Transcribed 25 videos from "Coding Tutorials" channel',
      createdAt: new Date(now.getTime() - 3 * 24 * 60 * 60 * 1000).toISOString(), // 3 days ago
      metadata: { jobId: 'job-002', videoCount: 25 }
    },
    {
      id: 'demo-6',
      userId: 'demo',
      amount: 500,
      type: 'purchase',
      description: 'High Volume Pack - 500 tokens',
      createdAt: new Date(now.getTime() - 5 * 24 * 60 * 60 * 1000).toISOString(), // 5 days ago
      metadata: { packageId: 'volume' }
    },
    {
      id: 'demo-7',
      userId: 'demo',
      amount: -1,
      type: 'usage',
      description: 'Single video transcription - "AI Revolution 2024"',
      createdAt: new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000).toISOString(), // 7 days ago
    }
  ]
  return transactions
}

const generateDemoBalance = (): UserTokenBalance => {
  return {
    userId: 'demo',
    balance: 660,
    lifetimeSpent: 41,
    lifetimePurchased: 700,
    lastPurchaseAt: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
    createdAt: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString(),
    updatedAt: new Date().toISOString()
  }
}

interface DemoJob {
  id: string
  title: string
  type: 'playlist' | 'channel' | 'single'
  status: 'completed' | 'processing' | 'failed'
  videoCount: number
  completedCount: number
  method: 'unofficial' | 'groq' | 'openai'
  createdAt: string
  completedAt?: string
}

const generateDemoJobs = (): DemoJob[] => {
  const now = new Date()
  return [
    {
      id: 'job-001',
      title: 'Tech Reviews 2024',
      type: 'playlist',
      status: 'completed',
      videoCount: 12,
      completedCount: 12,
      method: 'groq',
      createdAt: new Date(now.getTime() - 6 * 60 * 60 * 1000).toISOString(),
      completedAt: new Date(now.getTime() - 5.5 * 60 * 60 * 1000).toISOString()
    },
    {
      id: 'job-002',
      title: 'Coding Tutorials',
      type: 'channel',
      status: 'processing',
      videoCount: 45,
      completedCount: 32,
      method: 'unofficial',
      createdAt: new Date(now.getTime() - 2 * 60 * 60 * 1000).toISOString()
    },
    {
      id: 'job-003',
      title: 'Machine Learning Basics',
      type: 'playlist',
      status: 'completed',
      videoCount: 25,
      completedCount: 25,
      method: 'groq',
      createdAt: new Date(now.getTime() - 3 * 24 * 60 * 60 * 1000).toISOString(),
      completedAt: new Date(now.getTime() - 3 * 24 * 60 * 60 * 1000 + 45 * 60 * 1000).toISOString()
    },
    {
      id: 'job-004',
      title: 'How to Build a SaaS',
      type: 'single',
      status: 'completed',
      videoCount: 1,
      completedCount: 1,
      method: 'openai',
      createdAt: new Date(now.getTime() - 24 * 60 * 60 * 1000).toISOString(),
      completedAt: new Date(now.getTime() - 24 * 60 * 60 * 1000 + 5 * 60 * 1000).toISOString()
    },
    {
      id: 'job-005',
      title: 'Startup Interviews 2024',
      type: 'playlist',
      status: 'failed',
      videoCount: 8,
      completedCount: 3,
      method: 'groq',
      createdAt: new Date(now.getTime() - 4 * 24 * 60 * 60 * 1000).toISOString()
    }
  ]
}

export default function DashboardPage() {
  const { user, loading: authLoading } = useAuth()
  const router = useRouter()
  
  const [balance, setBalance] = useState<UserTokenBalance | null>(null)
  const [transactions, setTransactions] = useState<TokenTransaction[]>([])
  const [jobs, setJobs] = useState<DemoJob[]>([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [isDemo, setIsDemo] = useState(false)

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
      
      // If no real data, use demo data
      if (!balanceData || balanceData.balance === 0) {
        setBalance(generateDemoBalance())
        setTransactions(generateDemoTransactions())
        setJobs(generateDemoJobs())
        setIsDemo(true)
      } else {
        setBalance(balanceData)
        setTransactions(transactionData.transactions)
        setJobs([]) // TODO: Load real jobs when API is ready
        setIsDemo(false)
      }
    } catch (err) {
      console.error('Failed to load dashboard data:', err)
      // On error, show demo data
      setBalance(generateDemoBalance())
      setTransactions(generateDemoTransactions())
      setJobs(generateDemoJobs())
      setIsDemo(true)
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
              {isDemo && (
                <Badge variant="secondary" className="bg-yellow-500/10 text-yellow-500 border-yellow-500/20">
                  Demo Data
                </Badge>
              )}
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

          {/* Job History */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.5 }}
          >
            <Card className="bg-zinc-900 border-zinc-800">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-zinc-100">
                  <ListVideo className="h-5 w-5" />
                  Recent Jobs
                </CardTitle>
                <CardDescription className="text-zinc-500">
                  Your transcription job history
                </CardDescription>
              </CardHeader>
              <CardContent>
                {jobs.length === 0 ? (
                  <div className="text-center py-12">
                    <FileText className="h-12 w-12 text-zinc-600 mx-auto mb-4" />
                    <p className="text-zinc-500">No transcription jobs yet</p>
                    <Button
                      onClick={() => router.push('/bulk')}
                      className="mt-4"
                      variant="outline"
                    >
                      Start a bulk transcription
                    </Button>
                  </div>
                ) : (
                  <div className="space-y-4">
                    {jobs.map((job) => {
                      const getStatusIcon = () => {
                        switch (job.status) {
                          case 'completed':
                            return <CheckCircle className="h-4 w-4 text-green-500" />
                          case 'processing':
                            return <Loader2 className="h-4 w-4 text-blue-500 animate-spin" />
                          case 'failed':
                            return <XCircle className="h-4 w-4 text-red-500" />
                        }
                      }

                      const getStatusColor = () => {
                        switch (job.status) {
                          case 'completed':
                            return 'bg-green-500/10 text-green-500 border-green-500/20'
                          case 'processing':
                            return 'bg-blue-500/10 text-blue-500 border-blue-500/20'
                          case 'failed':
                            return 'bg-red-500/10 text-red-500 border-red-500/20'
                        }
                      }

                      const getTypeIcon = () => {
                        switch (job.type) {
                          case 'playlist':
                            return <ListVideo className="h-4 w-4 text-zinc-400" />
                          case 'channel':
                            return <PlayCircle className="h-4 w-4 text-zinc-400" />
                          case 'single':
                            return <FileText className="h-4 w-4 text-zinc-400" />
                        }
                      }

                      return (
                        <div
                          key={job.id}
                          className="flex items-center justify-between p-4 rounded-lg border border-zinc-800 bg-zinc-800/50 hover:bg-zinc-800 transition-colors"
                        >
                          <div className="flex items-center gap-4">
                            <div className="w-10 h-10 rounded-full bg-zinc-800 flex items-center justify-center">
                              {getTypeIcon()}
                            </div>
                            <div>
                              <div className="flex items-center gap-2">
                                <p className="font-medium text-zinc-100">{job.title}</p>
                                <Badge className={cn("text-xs", getStatusColor())}>
                                  <span className="mr-1">{getStatusIcon()}</span>
                                  {job.status}
                                </Badge>
                              </div>
                              <div className="flex items-center gap-4 mt-1">
                                <p className="text-sm text-zinc-500">
                                  {formatDate(job.createdAt)}
                                </p>
                                <p className="text-sm text-zinc-500">
                                  {job.completedCount}/{job.videoCount} videos
                                </p>
                                <Badge variant="secondary" className="text-xs">
                                  {job.method}
                                </Badge>
                              </div>
                            </div>
                          </div>
                          <div className="flex items-center gap-2">
                            {job.status === 'processing' && (
                              <div className="text-right mr-4">
                                <p className="text-sm font-medium text-zinc-300">
                                  {Math.round((job.completedCount / job.videoCount) * 100)}%
                                </p>
                                <div className="w-20 h-1 bg-zinc-800 rounded-full mt-1">
                                  <div
                                    className="h-full bg-blue-500 rounded-full transition-all"
                                    style={{ width: `${(job.completedCount / job.videoCount) * 100}%` }}
                                  />
                                </div>
                              </div>
                            )}
                            <Button
                              size="sm"
                              variant="ghost"
                              className="text-zinc-400 hover:text-zinc-100"
                              onClick={() => {
                                if (job.status === 'completed') {
                                  // TODO: Download transcripts
                                } else if (job.status === 'processing') {
                                  router.push(`/bulk?job=${job.id}`)
                                }
                              }}
                            >
                              {job.status === 'completed' ? 'Download' : 'View'}
                            </Button>
                          </div>
                        </div>
                      )
                    })}
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