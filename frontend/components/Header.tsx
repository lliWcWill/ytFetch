'use client'

import { useState, useEffect, useRef } from 'react'
import Link from 'next/link'
import { useRouter, usePathname } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { useAuth } from '@/providers/AuthProvider'
import { 
  User, 
  LogOut, 
  Settings, 
  CreditCard, 
  ChevronDown,
  Menu,
  X,
  Zap
} from 'lucide-react'

interface NavItem {
  href: string
  label: string
  badge?: string
}

const navigation: NavItem[] = [
  { href: '/', label: 'Transcribe' },
  { href: '/bulk', label: 'Bulk Process', badge: 'Pro' },
]

export default function Header() {
  const { user, signOut, loading } = useAuth()
  const router = useRouter()
  const pathname = usePathname()
  const [isProfileOpen, setIsProfileOpen] = useState(false)
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false)
  const profileRef = useRef<HTMLDivElement>(null)

  // Close profile dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (profileRef.current && !profileRef.current.contains(event.target as Node)) {
        setIsProfileOpen(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  // Close mobile menu on route change
  useEffect(() => {
    setIsMobileMenuOpen(false)
  }, [pathname])

  const handleSignOut = async () => {
    try {
      await signOut()
      setIsProfileOpen(false)
      router.push('/login')
    } catch (error) {
      console.error('Sign out error:', error)
    }
  }

  const handleSignIn = () => {
    // Store current path for redirect after login
    sessionStorage.setItem('auth-redirect-to', pathname)
    router.push('/login')
  }

  // Get user's initials for avatar
  const getUserInitials = (user: any) => {
    if (user?.user_metadata?.full_name) {
      return user.user_metadata.full_name
        .split(' ')
        .map((n: string) => n[0])
        .join('')
        .toUpperCase()
        .slice(0, 2)
    }
    if (user?.email) {
      return user.email.slice(0, 2).toUpperCase()
    }
    return 'U'
  }

  // Get user's display name
  const getUserDisplayName = (user: any) => {
    return user?.user_metadata?.full_name || user?.email || 'User'
  }

  return (
    <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="container mx-auto px-4">
        <div className="flex h-16 items-center justify-between">
          {/* Logo */}
          <Link href="/" className="flex items-center space-x-2">
            <div className="w-8 h-8 bg-gradient-to-r from-orange-500 to-red-500 rounded-lg flex items-center justify-center">
              <span className="text-sm font-bold text-white">yt</span>
            </div>
            <span className="font-bold text-xl">ytFetch</span>
          </Link>

          {/* Desktop Navigation */}
          <nav className="hidden md:flex items-center space-x-6">
            {navigation.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className={`text-sm font-medium transition-colors hover:text-primary ${
                  pathname === item.href 
                    ? 'text-foreground' 
                    : 'text-muted-foreground'
                } ${item.badge ? 'flex items-center space-x-1' : ''}`}
              >
                <span>{item.label}</span>
                {item.badge && (
                  <span className="px-1.5 py-0.5 text-xs bg-orange-500 text-white rounded-full">
                    {item.badge}
                  </span>
                )}
              </Link>
            ))}
          </nav>

          {/* User Menu */}
          <div className="flex items-center space-x-4">
            {/* Auth Section */}
            {loading ? (
              <div className="w-8 h-8 rounded-full bg-muted animate-pulse" />
            ) : user ? (
              <div className="relative" ref={profileRef}>
                <Button
                  variant="ghost"
                  className="relative h-8 w-8 rounded-full"
                  onClick={() => setIsProfileOpen(!isProfileOpen)}
                >
                  {user.user_metadata?.avatar_url ? (
                    <img
                      src={user.user_metadata.avatar_url}
                      alt="Profile"
                      className="h-8 w-8 rounded-full object-cover"
                    />
                  ) : (
                    <div className="h-8 w-8 rounded-full bg-orange-500 flex items-center justify-center text-white text-sm font-medium">
                      {getUserInitials(user)}
                    </div>
                  )}
                </Button>

                {/* Profile Dropdown */}
                {isProfileOpen && (
                  <div className="absolute right-0 mt-2 w-56 bg-background border rounded-md shadow-lg z-50">
                    <div className="px-3 py-2 border-b">
                      <p className="text-sm font-medium">{getUserDisplayName(user)}</p>
                      <p className="text-xs text-muted-foreground truncate">{user.email}</p>
                    </div>
                    
                    <div className="py-1">
                      <button
                        onClick={() => {
                          setIsProfileOpen(false)
                          router.push('/profile')
                        }}
                        className="flex w-full items-center px-3 py-2 text-sm hover:bg-muted"
                      >
                        <User className="mr-2 h-4 w-4" />
                        Profile
                      </button>
                      
                      <button
                        onClick={() => {
                          setIsProfileOpen(false)
                          router.push('/settings')
                        }}
                        className="flex w-full items-center px-3 py-2 text-sm hover:bg-muted"
                      >
                        <Settings className="mr-2 h-4 w-4" />
                        Settings
                      </button>
                      
                      <button
                        onClick={() => {
                          setIsProfileOpen(false)
                          router.push('/billing')
                        }}
                        className="flex w-full items-center px-3 py-2 text-sm hover:bg-muted"
                      >
                        <CreditCard className="mr-2 h-4 w-4" />
                        Billing
                      </button>
                      
                      <div className="border-t my-1"></div>
                      
                      <button
                        onClick={handleSignOut}
                        className="flex w-full items-center px-3 py-2 text-sm hover:bg-muted text-red-600"
                      >
                        <LogOut className="mr-2 h-4 w-4" />
                        Sign out
                      </button>
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <Button onClick={handleSignIn} size="sm">
                Sign In
              </Button>
            )}

            {/* Mobile Menu Button */}
            <Button
              variant="ghost"
              size="sm"
              className="md:hidden"
              onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
            >
              {isMobileMenuOpen ? (
                <X className="h-5 w-5" />
              ) : (
                <Menu className="h-5 w-5" />
              )}
            </Button>
          </div>
        </div>

        {/* Mobile Navigation */}
        {isMobileMenuOpen && (
          <div className="md:hidden border-t">
            <nav className="px-2 pt-2 pb-4 space-y-1">
              {navigation.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`block px-3 py-2 text-base font-medium transition-colors hover:text-primary hover:bg-muted rounded-md ${
                    pathname === item.href 
                      ? 'text-foreground bg-muted' 
                      : 'text-muted-foreground'
                  }`}
                >
                  <div className="flex items-center space-x-2">
                    <span>{item.label}</span>
                    {item.badge && (
                      <span className="px-1.5 py-0.5 text-xs bg-orange-500 text-white rounded-full">
                        {item.badge}
                      </span>
                    )}
                  </div>
                </Link>
              ))}
              
              {user && (
                <>
                  <div className="border-t my-2"></div>
                  <Link
                    href="/profile"
                    className="block px-3 py-2 text-base font-medium text-muted-foreground hover:text-primary hover:bg-muted rounded-md"
                  >
                    Profile
                  </Link>
                  <Link
                    href="/settings"
                    className="block px-3 py-2 text-base font-medium text-muted-foreground hover:text-primary hover:bg-muted rounded-md"
                  >
                    Settings
                  </Link>
                  <Link
                    href="/billing"
                    className="block px-3 py-2 text-base font-medium text-muted-foreground hover:text-primary hover:bg-muted rounded-md"
                  >
                    Billing
                  </Link>
                  <button
                    onClick={handleSignOut}
                    className="block w-full text-left px-3 py-2 text-base font-medium text-red-600 hover:bg-muted rounded-md"
                  >
                    Sign Out
                  </button>
                </>
              )}
            </nav>
          </div>
        )}
      </div>
    </header>
  )
}