'use client'

import { Button } from '@/components/ui/button'
import { useRouter } from 'next/navigation'
import { AlertCircle } from 'lucide-react'

export default function AuthCodeErrorPage() {
  const router = useRouter()

  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-4">
      <div className="max-w-md w-full space-y-6 text-center">
        <div className="mx-auto w-16 h-16 bg-destructive/10 rounded-full flex items-center justify-center">
          <AlertCircle className="h-8 w-8 text-destructive" />
        </div>
        
        <div className="space-y-2">
          <h1 className="text-2xl font-semibold">Authentication Error</h1>
          <p className="text-muted-foreground">
            There was an error during the authentication process. This could be due to an expired link or a configuration issue.
          </p>
        </div>

        <div className="space-y-3">
          <Button 
            onClick={() => router.push('/login')}
            size="lg"
            className="w-full"
          >
            Try Again
          </Button>
          
          <Button 
            onClick={() => router.push('/')}
            variant="outline"
            size="lg"
            className="w-full"
          >
            Go to Home
          </Button>
        </div>

        <p className="text-xs text-muted-foreground">
          If this error persists, please contact support.
        </p>
      </div>
    </div>
  )
}