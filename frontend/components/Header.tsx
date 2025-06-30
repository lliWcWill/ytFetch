'use client'

import { useState, useEffect, useRef } from 'react'
import Link from 'next/link'
import { useRouter, usePathname } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { useAuth } from '@/providers/AuthProvider'
import { TokenBalance } from '@/components/TokenBalance'
import { 
  User, 
  LogOut, 
  Settings, 
  CreditCard, 
  ChevronDown,
  Menu,
  X,
  Zap,
  Coins
} from 'lucide-react'

interface NavItem {
  href: string
  label: string
  badge?: string
  authRequired?: boolean
}

const navigation: NavItem[] = [
  { href: '/', label: 'Transcribe' },
  { href: '/bulk', label: 'Bulk Process' },
  { href: '/pricing', label: 'Pricing' },
  { href: '/dashboard', label: 'Dashboard', authRequired: true },
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
    <header className="sticky top-0 z-50 w-full border-b border-zinc-800 bg-zinc-950/95 backdrop-blur supports-[backdrop-filter]:bg-zinc-950/80">
      <div className="container mx-auto px-4">
        <div className="flex h-16 items-center justify-between">
          {/* Logo */}
          <Link href="/" className="flex items-center space-x-2 group">
            <div className="w-8 h-8 bg-gradient-to-r from-orange-500 to-orange-600 rounded-lg flex items-center justify-center shadow-lg shadow-orange-500/20 group-hover:shadow-orange-500/30 transition-shadow">
              <span className="text-sm font-bold text-white">yt</span>
            </div>
            <span className="font-bold text-xl text-zinc-100">ytFetch</span>
          </Link>

          {/* Desktop Navigation */}
          <nav className="hidden md:flex items-center space-x-6">
            {navigation.map((item) => {
              // Skip auth-required items if user is not logged in
              if (item.authRequired && !user) return null
              
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`text-sm font-medium transition-colors ${
                    pathname === item.href 
                      ? 'text-zinc-100' 
                      : 'text-zinc-400 hover:text-zinc-100'
                  } ${item.badge ? 'flex items-center space-x-1' : ''}`}
                >
                  <span>{item.label}</span>
                  {item.badge && (
                    <span className="px-1.5 py-0.5 text-xs bg-orange-500/20 text-orange-500 rounded-full border border-orange-500/30">
                      {item.badge}
                    </span>
                  )}
                </Link>
              )
            })}
          </nav>

          {/* User Menu */}
          <div className="flex items-center space-x-4">
            {/* Dashboard Button & Token Balance for authenticated users */}
            {user && !loading && (
              <>
                <div className="hidden md:block">
                  <TokenBalance variant="inline" showBuyButton={false} />
                </div>
                <Button
                  onClick={() => router.push('/dashboard')}
                  variant="outline"
                  size="sm"
                  className="hidden md:flex items-center gap-2 border-zinc-800 hover:bg-zinc-900 text-zinc-300 hover:text-zinc-100"
                >
                  <Coins className="w-4 h-4" />
                  Dashboard
                </Button>
              </>
            )}
            
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
                  <div className="absolute right-0 mt-2 w-56 bg-zinc-900 border border-zinc-800 rounded-md shadow-xl z-50">
                    <div className="px-3 py-2 border-b border-zinc-800">
                      <p className="text-sm font-medium text-zinc-100">{getUserDisplayName(user)}</p>
                      <p className="text-xs text-zinc-500 truncate">{user.email}</p>
                    </div>
                    
                    <div className="py-1">
                      <button
                        onClick={() => {
                          setIsProfileOpen(false)
                          router.push('/profile')
                        }}
                        className="flex w-full items-center px-3 py-2 text-sm text-zinc-300 hover:bg-zinc-800 hover:text-zinc-100 transition-colors"
                      >
                        <User className="mr-2 h-4 w-4" />
                        Profile
                      </button>
                      
                      <button
                        onClick={() => {
                          setIsProfileOpen(false)
                          router.push('/settings')
                        }}
                        className="flex w-full items-center px-3 py-2 text-sm text-zinc-300 hover:bg-zinc-800 hover:text-zinc-100 transition-colors"
                      >
                        <Settings className="mr-2 h-4 w-4" />
                        Settings
                      </button>
                      
                      <button
                        onClick={() => {
                          setIsProfileOpen(false)
                          router.push('/dashboard')
                        }}
                        className="flex w-full items-center px-3 py-2 text-sm text-zinc-300 hover:bg-zinc-800 hover:text-zinc-100 transition-colors"
                      >
                        <Coins className="mr-2 h-4 w-4" />
                        Token Dashboard
                      </button>
                      
                      <div className="border-t border-zinc-800 my-1"></div>
                      
                      <button
                        onClick={handleSignOut}
                        className="flex w-full items-center px-3 py-2 text-sm text-red-500 hover:bg-red-500/10 hover:text-red-400 transition-colors"
                      >
                        <LogOut className="mr-2 h-4 w-4" />
                        Sign out
                      </button>
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="flex items-center space-x-3">
                <Button 
                  onClick={handleSignIn} 
                  size="sm"
                  className="bg-zinc-800 text-zinc-300 hover:bg-zinc-700 hover:text-zinc-100 transition-colors"
                >
                  Sign In
                </Button>
                <Button 
                  onClick={handleSignIn} 
                  size="sm"
                  className="bg-gradient-to-r from-orange-500 to-orange-600 hover:from-orange-600 hover:to-orange-700 text-white shadow-lg shadow-orange-500/20"
                >
                  Sign Up
                </Button>
              </div>
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
          <div className="md:hidden border-t border-zinc-800 bg-zinc-950">
            <nav className="px-2 pt-2 pb-4 space-y-1">
              {navigation.map((item) => {
                // Skip auth-required items if user is not logged in
                if (item.authRequired && !user) return null
                
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`block px-3 py-2 text-base font-medium transition-colors rounded-md ${
                      pathname === item.href 
                        ? 'text-zinc-100 bg-zinc-800' 
                        : 'text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800'
                    }`}
                  >
                    <div className="flex items-center space-x-2">
                      <span>{item.label}</span>
                      {item.badge && (
                        <span className="px-1.5 py-0.5 text-xs bg-orange-500/20 text-orange-500 rounded-full border border-orange-500/30">
                          {item.badge}
                        </span>
                      )}
                    </div>
                  </Link>
                )
              })}
              
              {user && (
                <>
                  <div className="border-t border-zinc-800 my-2"></div>
                  <Link
                    href="/profile"
                    className="block px-3 py-2 text-base font-medium text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800 rounded-md transition-colors"
                  >
                    Profile
                  </Link>
                  <Link
                    href="/settings"
                    className="block px-3 py-2 text-base font-medium text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800 rounded-md transition-colors"
                  >
                    Settings
                  </Link>
                  <Link
                    href="/dashboard"
                    className="block px-3 py-2 text-base font-medium text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800 rounded-md transition-colors"
                  >
                    Token Dashboard
                  </Link>
                  <button
                    onClick={handleSignOut}
                    className="block w-full text-left px-3 py-2 text-base font-medium text-red-500 hover:bg-red-500/10 hover:text-red-400 rounded-md transition-colors"
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