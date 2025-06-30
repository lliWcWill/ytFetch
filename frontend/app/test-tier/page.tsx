'use client'

import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { UsageDisplay } from '@/components/UsageDisplay'
import { UpgradePrompt } from '@/components/UpgradePrompt'
import { useAuth } from '@/providers/AuthProvider'
import { ArrowLeft } from 'lucide-react'
import Link from 'next/link'

export default function TestTierPage() {
  const { user, profile, loading } = useAuth()
  const [showUpgradePrompt, setShowUpgradePrompt] = useState(false)
  const [upgradeReason, setUpgradeReason] = useState<'videos' | 'jobs' | 'concurrent' | 'duration'>('videos')

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="flex flex-col items-center space-y-4">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-orange-500"></div>
          <p className="text-sm text-muted-foreground">Loading...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-background">
      <div className="container mx-auto px-4 py-8">
        <div className="max-w-4xl mx-auto space-y-8">
          {/* Header */}
          <div className="flex items-center justify-between">
            <Button
              variant="ghost"
              asChild
              className="text-muted-foreground hover:text-foreground"
            >
              <Link href="/" className="flex items-center gap-2">
                <ArrowLeft className="h-4 w-4" />
                Back to Home
              </Link>
            </Button>
          </div>

          {/* Title */}
          <div className="text-center space-y-2">
            <h1 className="text-4xl font-bold">Tier System Test</h1>
            <p className="text-xl text-muted-foreground">
              Test the tier-aware UI components
            </p>
          </div>

          {/* Auth Status */}
          <Card>
            <CardHeader>
              <CardTitle>Authentication Status</CardTitle>
              <CardDescription>Current user and profile information</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-2 text-sm">
                <div>
                  <span className="font-medium">User ID:</span>{' '}
                  <span className="text-muted-foreground">{user?.id || 'Not authenticated'}</span>
                </div>
                <div>
                  <span className="font-medium">Email:</span>{' '}
                  <span className="text-muted-foreground">{user?.email || 'Not authenticated'}</span>
                </div>
                <div>
                  <span className="font-medium">Tier:</span>{' '}
                  <span className="text-muted-foreground">
                    {profile?.tier?.display_name || 'No tier data'}
                  </span>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Usage Display */}
          {user && profile && (
            <div>
              <h2 className="text-2xl font-semibold mb-4">Usage Display Component</h2>
              <UsageDisplay 
                onUpgradeClick={() => {
                  setUpgradeReason('jobs')
                  setShowUpgradePrompt(true)
                }}
              />
            </div>
          )}

          {/* Test Upgrade Prompts */}
          <Card>
            <CardHeader>
              <CardTitle>Test Upgrade Prompts</CardTitle>
              <CardDescription>Trigger different upgrade scenarios</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <Button 
                  onClick={() => {
                    setUpgradeReason('videos')
                    setShowUpgradePrompt(true)
                  }}
                >
                  Video Limit Exceeded
                </Button>
                <Button 
                  onClick={() => {
                    setUpgradeReason('jobs')
                    setShowUpgradePrompt(true)
                  }}
                >
                  Job Limit Exceeded
                </Button>
                <Button 
                  onClick={() => {
                    setUpgradeReason('concurrent')
                    setShowUpgradePrompt(true)
                  }}
                >
                  Concurrent Limit
                </Button>
                <Button 
                  onClick={() => {
                    setUpgradeReason('duration')
                    setShowUpgradePrompt(true)
                  }}
                >
                  Duration Limit
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Upgrade Prompt */}
          <UpgradePrompt
            open={showUpgradePrompt}
            onOpenChange={setShowUpgradePrompt}
            reason={upgradeReason}
            recommendedTier={profile?.tier?.name === 'free' ? 'pro' : 'enterprise'}
          />
        </div>
      </div>
    </div>
  )
}