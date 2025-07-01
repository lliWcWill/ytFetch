"use client"

import * as React from "react"
import { cn } from "@/lib/utils"

interface TooltipContextValue {
  open: boolean
  setOpen: (open: boolean) => void
}

const TooltipContext = React.createContext<TooltipContextValue | undefined>(undefined)

interface TooltipProviderProps {
  children: React.ReactNode
  delayDuration?: number
}

const TooltipProvider = ({ children, delayDuration = 700 }: TooltipProviderProps) => {
  return <>{children}</>
}

interface TooltipProps {
  children: React.ReactNode
  defaultOpen?: boolean
  open?: boolean
  onOpenChange?: (open: boolean) => void
}

const Tooltip = ({ children, defaultOpen = false, open: controlledOpen, onOpenChange }: TooltipProps) => {
  const [uncontrolledOpen, setUncontrolledOpen] = React.useState(defaultOpen)
  const open = controlledOpen !== undefined ? controlledOpen : uncontrolledOpen
  const setOpen = React.useCallback(
    (newOpen: boolean) => {
      if (controlledOpen === undefined) {
        setUncontrolledOpen(newOpen)
      }
      onOpenChange?.(newOpen)
    },
    [controlledOpen, onOpenChange]
  )

  return (
    <TooltipContext.Provider value={{ open, setOpen }}>
      <div className="relative inline-flex">{children}</div>
    </TooltipContext.Provider>
  )
}

interface TooltipTriggerProps {
  children: React.ReactNode
  asChild?: boolean
}

const TooltipTrigger = React.forwardRef<HTMLDivElement, TooltipTriggerProps>(
  ({ children, asChild = false, ...props }, ref) => {
    const context = React.useContext(TooltipContext)
    if (!context) throw new Error("TooltipTrigger must be used within Tooltip")

    const { setOpen } = context

    const handleMouseEnter = () => setOpen(true)
    const handleMouseLeave = () => setOpen(false)
    const handleFocus = () => setOpen(true)
    const handleBlur = () => setOpen(false)

    if (asChild && React.isValidElement(children)) {
      return React.cloneElement(children as React.ReactElement<any>, {
        ref,
        onMouseEnter: handleMouseEnter,
        onMouseLeave: handleMouseLeave,
        onFocus: handleFocus,
        onBlur: handleBlur,
        ...props,
      })
    }

    return (
      <div
        ref={ref}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
        onFocus={handleFocus}
        onBlur={handleBlur}
        {...props}
      >
        {children}
      </div>
    )
  }
)
TooltipTrigger.displayName = "TooltipTrigger"

interface TooltipContentProps extends React.HTMLAttributes<HTMLDivElement> {
  side?: "top" | "right" | "bottom" | "left"
  sideOffset?: number
}

const TooltipContent = React.forwardRef<HTMLDivElement, TooltipContentProps>(
  ({ className, side = "top", sideOffset = 4, children, ...props }, ref) => {
    const context = React.useContext(TooltipContext)
    if (!context) throw new Error("TooltipContent must be used within Tooltip")

    const { open } = context

    if (!open) return null

    const sideStyles = {
      top: `bottom-full left-1/2 -translate-x-1/2 mb-${sideOffset/4}`,
      bottom: `top-full left-1/2 -translate-x-1/2 mt-${sideOffset/4}`,
      left: `right-full top-1/2 -translate-y-1/2 mr-${sideOffset/4}`,
      right: `left-full top-1/2 -translate-y-1/2 ml-${sideOffset/4}`,
    }

    return (
      <div
        ref={ref}
        className={cn(
          "absolute z-50 overflow-hidden rounded-md bg-zinc-900 px-3 py-1.5 text-xs text-zinc-50",
          "animate-in fade-in-0 zoom-in-95",
          "pointer-events-none whitespace-nowrap",
          "shadow-md",
          sideStyles[side],
          className
        )}
        {...props}
      >
        {children}
        {/* Arrow */}
        <div
          className={cn(
            "absolute w-2 h-2 bg-zinc-900 rotate-45",
            side === "top" && "top-full left-1/2 -translate-x-1/2 -translate-y-1/2",
            side === "bottom" && "bottom-full left-1/2 -translate-x-1/2 translate-y-1/2",
            side === "left" && "left-full top-1/2 -translate-y-1/2 -translate-x-1/2",
            side === "right" && "right-full top-1/2 -translate-y-1/2 translate-x-1/2"
          )}
        />
      </div>
    )
  }
)
TooltipContent.displayName = "TooltipContent"

export { Tooltip, TooltipTrigger, TooltipContent, TooltipProvider }