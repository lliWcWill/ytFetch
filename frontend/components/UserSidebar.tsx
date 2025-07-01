'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { useAuth } from '@/providers/AuthProvider'
import { useSidebar } from '@/contexts/SidebarContext'
import { Button } from '@/components/ui/button'
import { TokenBalance } from '@/components/TokenBalance'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import {
  LayoutDashboard,
  Settings,
  Coins,
  LogOut,
  ChevronLeft,
  ChevronRight,
  User,
  Menu,
  Sparkles,
  FileText,
  CreditCard
} from 'lucide-react'

interface SidebarItem {
  href: string
  label: string
  icon: React.ComponentType<{ className?: string }>
  badge?: string
  comingSoon?: boolean
}

const sidebarItems: SidebarItem[] = [
  { 
    href: '/dashboard', 
    label: 'Dashboard', 
    icon: LayoutDashboard 
  },
  { 
    href: '/profile', 
    label: 'Profile', 
    icon: User 
  },
  { 
    href: '/billing', 
    label: 'Billing & Tokens', 
    icon: CreditCard 
  },
  { 
    href: '/settings', 
    label: 'Settings', 
    icon: Settings 
  },
  { 
    href: '/api-docs', 
    label: 'API Docs', 
    icon: FileText,
    comingSoon: true 
  },
  { 
    href: '/integrations', 
    label: 'Integrations', 
    icon: Sparkles,
    comingSoon: true 
  },
]

export default function UserSidebar() {
  const { user, signOut } = useAuth()
  const pathname = usePathname()
  const router = useRouter()
  const { isExpanded, setIsExpanded } = useSidebar()
  const [isMobileOpen, setIsMobileOpen] = useState(false)

  // Close mobile sidebar on route change
  useEffect(() => {
    setIsMobileOpen(false)
  }, [pathname])

  // Listen for auth state changes to force re-render
  useEffect(() => {
    const handleAuthStateChange = () => {
      console.log('Auth state changed in sidebar, forcing re-render')
      // Force a re-render by updating mobile open state
      setIsMobileOpen(false)
    }

    window.addEventListener('auth-state-changed', handleAuthStateChange)
    return () => window.removeEventListener('auth-state-changed', handleAuthStateChange)
  }, [])

  // Don't render sidebar for guests
  if (!user) return null

  const handleSignOut = async () => {
    try {
      await signOut()
      router.push('/login')
    } catch (error) {
      console.error('Sign out error:', error)
    }
  }

  // Get user's initials for avatar
  const getUserInitials = () => {
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
  const getUserDisplayName = () => {
    return user?.user_metadata?.full_name || user?.email || 'User'
  }

  const sidebarContent = (
    <TooltipProvider delayDuration={300}>
      {/* Hamburger Menu at the top */}
      <div className="p-2 border-b border-zinc-800">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setIsExpanded(!isExpanded)}
          className={`w-full ${isExpanded ? 'justify-start' : 'justify-center'} p-2 hover:bg-zinc-800/50`}
        >
          {isExpanded ? (
            <>
              <ChevronRight className="h-5 w-5" />
              <span className="ml-3 text-sm font-medium">Collapse</span>
            </>
          ) : (
            <ChevronLeft className="h-5 w-5" />
          )}
        </Button>
      </div>

      {/* User Profile Section */}
      <div className={`p-4 border-b border-zinc-800 ${!isExpanded && !isMobileOpen ? 'px-2' : ''}`}>
        <div className={`flex items-center ${!isExpanded && !isMobileOpen ? 'justify-center' : 'space-x-3'}`}>
          {user.user_metadata?.avatar_url ? (
            <img
              src={user.user_metadata.avatar_url}
              alt="Profile"
              className="h-10 w-10 rounded-full object-cover flex-shrink-0"
            />
          ) : (
            <div className="h-10 w-10 rounded-full bg-gradient-to-r from-orange-500 to-orange-600 flex items-center justify-center text-white font-medium flex-shrink-0">
              {getUserInitials()}
            </div>
          )}
          {isExpanded && (
            <>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-zinc-100 truncate">{getUserDisplayName()}</p>
                <p className="text-xs text-zinc-500 truncate">{user.email}</p>
              </div>
            </>
          )}
        </div>
        
        {/* Token Balance */}
        {isExpanded && (
          <div className="mt-4">
            <TokenBalance variant="compact" showBuyButton={true} />
          </div>
        )}
        {!isExpanded && !isMobileOpen && (
          <Tooltip>
            <TooltipTrigger asChild>
              <div className="mt-3 flex justify-center">
                <Coins className="h-5 w-5 text-zinc-400" />
              </div>
            </TooltipTrigger>
            <TooltipContent side="left">
              <p>Token Balance</p>
            </TooltipContent>
          </Tooltip>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-2 space-y-1 overflow-y-auto">
        {sidebarItems.map((item) => {
          const Icon = item.icon
          const isActive = pathname === item.href
          
          const linkContent = (
            <Link
              key={item.href}
              href={item.comingSoon ? '#' : item.href}
              className={`
                flex items-center px-3 py-2 text-sm font-medium rounded-md transition-colors
                ${isActive 
                  ? 'bg-zinc-800 text-zinc-100' 
                  : item.comingSoon
                    ? 'text-zinc-600 cursor-not-allowed'
                    : 'text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800/50'
                }
                ${!isExpanded && !isMobileOpen ? 'justify-center' : ''}
              `}
              onClick={item.comingSoon ? (e) => e.preventDefault() : undefined}
            >
              <Icon className={`h-5 w-5 flex-shrink-0 ${isExpanded || isMobileOpen ? 'mr-3' : ''}`} />
              {(isExpanded || isMobileOpen) && (
                <span className="flex-1 flex items-center justify-between">
                  {item.label}
                  {item.comingSoon && (
                    <span className="text-xs text-zinc-600 ml-2">Soon</span>
                  )}
                  {item.badge && (
                    <span className="ml-2 px-2 py-0.5 text-xs bg-orange-500/20 text-orange-500 rounded-full">
                      {item.badge}
                    </span>
                  )}
                </span>
              )}
            </Link>
          )

          // Wrap in tooltip for collapsed state
          if (!isExpanded && !isMobileOpen) {
            return (
              <Tooltip key={item.href}>
                <TooltipTrigger asChild>
                  {linkContent}
                </TooltipTrigger>
                <TooltipContent side="left">
                  <p>{item.label}</p>
                  {item.comingSoon && <p className="text-xs text-zinc-400">Coming Soon</p>}
                </TooltipContent>
              </Tooltip>
            )
          }

          return linkContent
        })}
      </nav>

      {/* Logout Button */}
      <div className="p-2 border-t border-zinc-800">
        {!isExpanded && !isMobileOpen ? (
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                onClick={handleSignOut}
                variant="ghost"
                className="w-full text-red-500 hover:text-red-400 hover:bg-red-500/10 px-2"
              >
                <LogOut className="h-5 w-5" />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="left">
              <p>Sign Out</p>
            </TooltipContent>
          </Tooltip>
        ) : (
          <Button
            onClick={handleSignOut}
            variant="ghost"
            className="w-full text-red-500 hover:text-red-400 hover:bg-red-500/10"
          >
            <LogOut className={`h-5 w-5 ${isExpanded || isMobileOpen ? 'mr-3' : ''}`} />
            {(isExpanded || isMobileOpen) && <span>Sign Out</span>}
          </Button>
        )}
      </div>

    </TooltipProvider>
  )

  return (
    <>
      {/* Mobile Toggle Button */}
      <Button
        variant="ghost"
        size="sm"
        onClick={() => setIsMobileOpen(!isMobileOpen)}
        className="fixed top-4 right-4 z-50 lg:hidden"
      >
        <Menu className="h-5 w-5" />
      </Button>

      {/* Mobile Sidebar Overlay */}
      {isMobileOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 lg:hidden"
          onClick={() => setIsMobileOpen(false)}
        />
      )}

      {/* Desktop Sidebar */}
      <aside className={`
        hidden lg:flex flex-col
        fixed right-0 top-0 h-full
        bg-zinc-950 border-l border-zinc-800
        transition-all duration-300 ease-in-out z-[60]
        ${isExpanded ? 'w-64' : 'w-16'}
      `}>
        {sidebarContent}
      </aside>

      {/* Mobile Sidebar */}
      <aside className={`
        lg:hidden flex flex-col
        fixed right-0 top-0 h-full w-64
        bg-zinc-950 border-l border-zinc-800
        transform transition-transform duration-300 z-[60]
        ${isMobileOpen ? 'translate-x-0' : 'translate-x-full'}
      `}>
        {sidebarContent}
      </aside>
    </>
  )
}