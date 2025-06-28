'use client'

import { useAuth } from '@/providers/AuthProvider'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Settings, Bell, Download, Trash2 } from 'lucide-react'

export default function SettingsPage() {
  const { user, loading, signOut } = useAuth()

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="flex flex-col items-center space-y-4">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-orange-500"></div>
          <p className="text-sm text-muted-foreground">Loading settings...</p>
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
            <h1 className="text-2xl font-semibold">Settings Access</h1>
            <p className="text-muted-foreground">Sign in to access your settings</p>
          </div>
          <Button 
            onClick={() => {
              sessionStorage.setItem('auth-redirect-to', '/settings')
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
        <div className="flex items-center space-x-3">
          <Settings className="h-8 w-8 text-orange-500" />
          <div>
            <h1 className="text-3xl font-bold">Settings</h1>
            <p className="text-muted-foreground">Manage your account preferences</p>
          </div>
        </div>

        {/* Settings Sections */}
        <div className="space-y-6">
          
          {/* Default Preferences */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Download className="h-5 w-5" />
                Default Preferences
              </CardTitle>
              <CardDescription>Set your default transcription options</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">Default Output Format</label>
                <select className="w-full p-2 border rounded-md bg-background">
                  <option value="txt">TXT - Plain Text</option>
                  <option value="srt">SRT - Subtitle Format</option>
                  <option value="vtt">VTT - Web Video Text</option>
                  <option value="json">JSON - Structured Data</option>
                </select>
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">Default Transcription Method</label>
                <select className="w-full p-2 border rounded-md bg-background">
                  <option value="groq">Groq AI - Best Quality</option>
                  <option value="unofficial">Unofficial - Faster</option>
                </select>
              </div>
              <Button>Save Preferences</Button>
            </CardContent>
          </Card>

          {/* Notifications */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Bell className="h-5 w-5" />
                Notifications
              </CardTitle>
              <CardDescription>Control how you receive updates</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium">Job Completion Emails</p>
                  <p className="text-sm text-muted-foreground">Get notified when transcription jobs complete</p>
                </div>
                <input type="checkbox" className="h-4 w-4" defaultChecked />
              </div>
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium">Weekly Usage Reports</p>
                  <p className="text-sm text-muted-foreground">Receive weekly summaries of your activity</p>
                </div>
                <input type="checkbox" className="h-4 w-4" />
              </div>
              <Button>Save Notification Settings</Button>
            </CardContent>
          </Card>

          {/* Account Actions */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Trash2 className="h-5 w-5" />
                Account Actions
              </CardTitle>
              <CardDescription>Manage your account</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-4">
                <div>
                  <Button variant="outline" className="w-full justify-start">
                    Download My Data
                  </Button>
                  <p className="text-xs text-muted-foreground mt-1">
                    Download all your transcriptions and account data
                  </p>
                </div>
                <div>
                  <Button 
                    variant="outline" 
                    className="w-full justify-start"
                    onClick={signOut}
                  >
                    Sign Out
                  </Button>
                  <p className="text-xs text-muted-foreground mt-1">
                    Sign out of your account on this device
                  </p>
                </div>
                <div>
                  <Button variant="destructive" className="w-full justify-start">
                    Delete Account
                  </Button>
                  <p className="text-xs text-muted-foreground mt-1">
                    Permanently delete your account and all data
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>

        </div>
      </div>
    </div>
  )
}