'use client'

import { createContext, useContext, useState, useEffect, ReactNode } from 'react'

interface SidebarContextType {
  isExpanded: boolean
  setIsExpanded: (expanded: boolean) => void
}

const SidebarContext = createContext<SidebarContextType | undefined>(undefined)

export function useSidebar() {
  const context = useContext(SidebarContext)
  if (!context) {
    throw new Error('useSidebar must be used within a SidebarProvider')
  }
  return context
}

interface SidebarProviderProps {
  children: ReactNode
}

export function SidebarProvider({ children }: SidebarProviderProps) {
  const [isExpanded, setIsExpanded] = useState(() => {
    // Check localStorage on initial load
    if (typeof window !== 'undefined') {
      const stored = localStorage.getItem('sidebarExpanded')
      return stored !== null ? stored === 'true' : true
    }
    return true
  })

  // Save to localStorage whenever the state changes
  useEffect(() => {
    localStorage.setItem('sidebarExpanded', String(isExpanded))
  }, [isExpanded])

  return (
    <SidebarContext.Provider value={{ isExpanded, setIsExpanded }}>
      {children}
    </SidebarContext.Provider>
  )
}