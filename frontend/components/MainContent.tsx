'use client'

import { ReactNode } from 'react'
import { useAuth } from '@/providers/AuthProvider'
import { useSidebar } from '@/contexts/SidebarContext'

interface MainContentProps {
  children: ReactNode
}

export default function MainContent({ children }: MainContentProps) {
  const { user } = useAuth()
  const { isExpanded } = useSidebar()

  return (
    <main 
      className={`
        flex-1 transition-all duration-300
        ${user ? (isExpanded ? 'lg:pr-64' : 'lg:pr-16') : ''}
      `}
    >
      {children}
    </main>
  )
}