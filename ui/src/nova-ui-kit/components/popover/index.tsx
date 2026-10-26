import * as PopoverPrimitive from '@radix-ui/react-popover'
import { cn } from 'nova-ui-kit/utils'
import * as React from 'react'

const Root = PopoverPrimitive.Root
Root.displayName = 'Popover.Root'

const Trigger = PopoverPrimitive.Trigger
Trigger.displayName = 'Popover.Trigger'

const Portal = PopoverPrimitive.Portal
Portal.displayName = 'Popover.Portal'

const Content = React.forwardRef<
  React.ElementRef<typeof PopoverPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof PopoverPrimitive.Content>
>(({ className, align = 'start', sideOffset = 4, ...props }, ref) => (
  <PopoverPrimitive.Content
    ref={ref}
    align={align}
    sideOffset={sideOffset}
    className={cn(
      'z-50 w-72 rounded-md border border-border bg-popover p-4 text-popover-foreground shadow-md outline-none data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 data-[side=bottom]:slide-in-from-top-2 data-[side=left]:slide-in-from-right-2 data-[side=right]:slide-in-from-left-2 data-[side=top]:slide-in-from-bottom-2',
      className
    )}
    {...props}
  />
))
Content.displayName = 'Popover.Content'

export { Content, Portal, Root, Trigger }
