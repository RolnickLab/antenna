import * as TooltipPrimitive from '@radix-ui/react-tooltip'
import { cn } from 'nova-ui-kit/utils'
import * as React from 'react'

const Provider = TooltipPrimitive.Provider

const Root = TooltipPrimitive.Root

const Trigger = TooltipPrimitive.Trigger

const Portal = TooltipPrimitive.Portal

const Content = React.forwardRef<
  React.ElementRef<typeof TooltipPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof TooltipPrimitive.Content>
>(({ className, sideOffset = 4, ...props }, ref) => (
  <TooltipPrimitive.Content
    ref={ref}
    sideOffset={sideOffset}
    className={cn(
      'z-50 overflow-hidden rounded-md border border-border bg-popover px-3 py-1.5 body-small text-foreground font-normal text-popover-foreground shadow-md animate-in fade-in-0 zoom-in-95 data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95 data-[side=bottom]:slide-in-from-top-2 data-[side=left]:slide-in-from-right-2 data-[side=right]:slide-in-from-left-2 data-[side=top]:slide-in-from-bottom-2 [&>span]:pt-0.5',
      className
    )}
    {...props}
  />
))
Content.displayName = TooltipPrimitive.Content.displayName

export { Content, Portal, Provider, Root, Trigger }
