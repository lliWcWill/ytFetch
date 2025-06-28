'use client'

import { useAuth } from '@/providers/AuthProvider'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { CreditCard, Check, Zap, Crown, Rocket } from 'lucide-react'

const plans = [
  {
    name: 'Free',
    price: '$0',
    period: '/month',
    description: 'Perfect for trying out ytFetch',
    features: [
      '5 transcriptions per month',
      'Basic output formats (TXT, SRT)',
      'Community support',
      'Standard processing speed'
    ],
    current: true,
    cta: 'Current Plan'
  },
  {
    name: 'Pro',
    price: '$19',
    period: '/month',
    description: 'Ideal for content creators and professionals',
    features: [
      '100 transcriptions per month',
      'All output formats (TXT, SRT, VTT, JSON)',
      'Bulk playlist processing',
      'Priority processing speed',
      'Email support',
      'Export to cloud storage'
    ],
    current: false,
    cta: 'Upgrade to Pro',
    popular: true
  },
  {
    name: 'Enterprise',
    price: '$99',
    period: '/month',
    description: 'For teams and heavy users',
    features: [
      'Unlimited transcriptions',
      'All output formats',
      'Unlimited bulk processing',
      'Lightning-fast processing',
      'Priority support',
      'API access',
      'Custom integrations',
      'Advanced analytics'
    ],
    current: false,
    cta: 'Contact Sales'
  }
]

export default function BillingPage() {
  const { user, loading } = useAuth()

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="flex flex-col items-center space-y-4">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-orange-500"></div>
          <p className="text-sm text-muted-foreground">Loading billing...</p>
        </div>
      </div>
    )
  }

  if (!user) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background p-4">
        <div className="text-center space-y-6 max-w-md">
          <div className="mx-auto w-16 h-16 bg-gradient-to-r from-orange-500 to-red-500 rounded-xl flex items-center justify-center">
            <span className="text-2xl font-bold text-white">yt</span>
          </div>
          <div className="space-y-2">
            <h1 className="text-2xl font-semibold">Billing Access</h1>
            <p className="text-muted-foreground">Sign in to manage your subscription</p>
          </div>
          <Button 
            onClick={() => {
              sessionStorage.setItem('auth-redirect-to', '/billing')
              window.location.href = '/login'
            }}
            size="lg" 
            className="w-full"
          >
            Sign In
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="container mx-auto px-4 py-8 max-w-6xl">
      <div className="space-y-8">
        {/* Header */}
        <div className="flex items-center space-x-3">
          <CreditCard className="h-8 w-8 text-orange-500" />
          <div>
            <h1 className="text-3xl font-bold">Billing & Plans</h1>
            <p className="text-muted-foreground">Manage your subscription and billing</p>
          </div>
        </div>

        {/* Current Plan */}
        <Card>
          <CardHeader>
            <CardTitle>Current Plan</CardTitle>
            <CardDescription>Your active subscription details</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-4">
                <div className="w-12 h-12 bg-orange-100 rounded-lg flex items-center justify-center">
                  <Zap className="h-6 w-6 text-orange-600" />
                </div>
                <div>
                  <p className="font-semibold">Free Plan</p>
                  <p className="text-sm text-muted-foreground">5 transcriptions per month</p>
                </div>
              </div>
              <div className="text-right">
                <p className="text-2xl font-bold">$0</p>
                <p className="text-sm text-muted-foreground">/month</p>
              </div>
            </div>
            <div className="mt-4 pt-4 border-t">
              <div className="flex items-center justify-between text-sm">
                <span>Usage this month</span>
                <span className="text-muted-foreground">0 / 5 transcriptions</span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2 mt-2">
                <div className="bg-orange-500 h-2 rounded-full" style={{ width: '0%' }}></div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Available Plans */}
        <div>
          <h2 className="text-2xl font-bold mb-6">Choose Your Plan</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {plans.map((plan, index) => (
              <Card key={plan.name} className={`relative ${plan.popular ? 'border-orange-500 shadow-lg' : ''}`}>
                {plan.popular && (
                  <div className="absolute -top-3 left-1/2 transform -translate-x-1/2">
                    <Badge className="bg-orange-500 text-white">Most Popular</Badge>
                  </div>
                )}
                <CardHeader className="text-center">
                  <div className="mx-auto w-12 h-12 rounded-lg flex items-center justify-center mb-4">
                    {index === 0 && <Zap className="h-6 w-6 text-gray-600" />}
                    {index === 1 && <Crown className="h-6 w-6 text-orange-600" />}
                    {index === 2 && <Rocket className="h-6 w-6 text-purple-600" />}
                  </div>
                  <CardTitle className="text-xl">{plan.name}</CardTitle>
                  <div className="flex items-baseline justify-center space-x-1">
                    <span className="text-3xl font-bold">{plan.price}</span>
                    <span className="text-muted-foreground">{plan.period}</span>
                  </div>
                  <CardDescription>{plan.description}</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <ul className="space-y-2">
                    {plan.features.map((feature, i) => (
                      <li key={i} className="flex items-center space-x-2 text-sm">
                        <Check className="h-4 w-4 text-green-500 flex-shrink-0" />
                        <span>{feature}</span>
                      </li>
                    ))}
                  </ul>
                  <Button 
                    className={`w-full ${plan.current ? 'bg-gray-200 text-gray-600 cursor-not-allowed' : ''}`}
                    disabled={plan.current}
                    variant={plan.popular ? 'default' : 'outline'}
                  >
                    {plan.cta}
                  </Button>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>

        {/* Billing History */}
        <Card>
          <CardHeader>
            <CardTitle>Billing History</CardTitle>
            <CardDescription>Your recent invoices and payments</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-center py-8 text-muted-foreground">
              <CreditCard className="h-12 w-12 mx-auto mb-4 opacity-50" />
              <p>No billing history yet</p>
              <p className="text-sm">Upgrade to a paid plan to see your invoices here</p>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}