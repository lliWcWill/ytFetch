'use client'

import { useAuth } from '@/providers/AuthProvider'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { User, Mail, Calendar, Shield } from 'lucide-react'

export default function ProfilePage() {
  const { user, loading } = useAuth()

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="flex flex-col items-center space-y-4">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-orange-500"></div>
          <p className="text-sm text-muted-foreground">Loading profile...</p>
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
            <h1 className="text-2xl font-semibold">Profile Access</h1>
            <p className="text-muted-foreground">Sign in to view your profile</p>
          </div>
          <Button 
            onClick={() => {
              sessionStorage.setItem('auth-redirect-to', '/profile')
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
    <div className="container mx-auto px-4 py-8 max-w-4xl">
      <div className="space-y-8">
        {/* Header */}
        <div className="flex items-center space-x-4">
          <div className="w-20 h-20 rounded-full bg-orange-500 flex items-center justify-center text-white text-2xl font-bold">
            {user.user_metadata?.avatar_url ? (
              <img
                src={user.user_metadata.avatar_url}
                alt="Profile"
                className="w-20 h-20 rounded-full object-cover"
              />
            ) : (
              user.email?.slice(0, 2).toUpperCase()
            )}
          </div>
          <div>
            <h1 className="text-3xl font-bold">
              {user.user_metadata?.full_name || 'Your Profile'}
            </h1>
            <p className="text-muted-foreground">{user.email}</p>
          </div>
        </div>

        {/* Profile Information */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <User className="h-5 w-5" />
                Account Information
              </CardTitle>
              <CardDescription>Your basic account details</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center gap-3">
                <Mail className="h-4 w-4 text-muted-foreground" />
                <div>
                  <p className="text-sm font-medium">Email</p>
                  <p className="text-sm text-muted-foreground">{user.email}</p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <Calendar className="h-4 w-4 text-muted-foreground" />
                <div>
                  <p className="text-sm font-medium">Member Since</p>
                  <p className="text-sm text-muted-foreground">
                    {new Date(user.created_at).toLocaleDateString()}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <Shield className="h-4 w-4 text-muted-foreground" />
                <div>
                  <p className="text-sm font-medium">Account Status</p>
                  <p className="text-sm text-green-600">Active</p>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Subscription</CardTitle>
              <CardDescription>Your current plan and usage</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium">Plan</span>
                  <span className="text-sm bg-orange-100 text-orange-800 px-2 py-1 rounded-full">
                    Free Tier
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium">Transcriptions this month</span>
                  <span className="text-sm text-muted-foreground">0 / 10</span>
                </div>
                <Button className="w-full">
                  Upgrade Plan
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Usage Statistics */}
        <Card>
          <CardHeader>
            <CardTitle>Usage Statistics</CardTitle>
            <CardDescription>Your transcription activity</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="text-center">
                <div className="text-2xl font-bold text-orange-500">0</div>
                <div className="text-sm text-muted-foreground">Total Transcriptions</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-blue-500">0</div>
                <div className="text-sm text-muted-foreground">Bulk Jobs</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-green-500">0 min</div>
                <div className="text-sm text-muted-foreground">Total Content</div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}