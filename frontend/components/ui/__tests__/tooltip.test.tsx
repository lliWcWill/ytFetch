import React from 'react'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Tooltip, TooltipTrigger, TooltipContent, TooltipProvider } from '../tooltip'

describe('Tooltip', () => {
  it('shows tooltip on hover', async () => {
    const user = userEvent.setup()
    
    render(
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger>
            <button>Hover me</button>
          </TooltipTrigger>
          <TooltipContent>
            <p>Tooltip content</p>
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    )

    const trigger = screen.getByText('Hover me')
    
    // Initially tooltip should not be visible
    expect(screen.queryByText('Tooltip content')).not.toBeInTheDocument()
    
    // Hover over trigger
    await user.hover(trigger)
    
    // Tooltip should appear
    await waitFor(() => {
      expect(screen.getByText('Tooltip content')).toBeInTheDocument()
    })
    
    // Move mouse away
    await user.unhover(trigger)
    
    // Tooltip should disappear
    await waitFor(() => {
      expect(screen.queryByText('Tooltip content')).not.toBeInTheDocument()
    })
  })

  it('supports different sides', () => {
    render(
      <TooltipProvider>
        <Tooltip defaultOpen={true}>
          <TooltipTrigger>
            <button>Trigger</button>
          </TooltipTrigger>
          <TooltipContent side="left">
            <p>Left tooltip</p>
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    )

    const tooltip = screen.getByText('Left tooltip').parentElement
    expect(tooltip).toHaveClass('right-full')
  })

  it('works with asChild prop', async () => {
    const user = userEvent.setup()
    
    render(
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>
            <a href="#">Link trigger</a>
          </TooltipTrigger>
          <TooltipContent>
            <p>Tooltip for link</p>
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    )

    const trigger = screen.getByText('Link trigger')
    
    await user.hover(trigger)
    
    await waitFor(() => {
      expect(screen.getByText('Tooltip for link')).toBeInTheDocument()
    })
  })
})