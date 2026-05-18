import * as SelectPrimitive from '@radix-ui/react-select'
import { cn } from 'design-system/utils'
import { Check, ChevronDown, ChevronUp, Loader2 } from 'lucide-react'
import * as React from 'react'

const Root = SelectPrimitive.Root
Root.displayName = 'Select.Root'

const Value = SelectPrimitive.Value
Value.displayName = 'Select.Value'

const Portal = SelectPrimitive.Portal
Portal.displayName = 'Select.Portal'

const Trigger = React.forwardRef<
  React.ElementRef<typeof SelectPrimitive.Trigger>,
  React.ComponentPropsWithoutRef<typeof SelectPrimitive.Trigger> & {
    hideIcon?: boolean
    loading?: boolean
  }
>(({ children, className, hideIcon, loading, ...props }, ref) => (
  <SelectPrimitive.Trigger
    ref={ref}
    className={cn(
      'flex h-12 w-full items-center justify-between text-left rounded-md border border-input bg-background text-muted-foreground px-4 body-base ring-offset-background placeholder:text-muted-foreground/50 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 [&>span]:line-clamp-1 [&>span]:pt-0.5 hover:bg-muted',
      className
    )}
    {...props}
  >
    {children}
    {!hideIcon ? (
      <SelectPrimitive.Icon asChild>
        {loading ? (
          <Loader2 className="h-4 w-4 shrink-0 animate-spin" />
        ) : (
          <ChevronDown className="h-4 w-4 shrink-0" />
        )}
      </SelectPrimitive.Icon>
    ) : null}
  </SelectPrimitive.Trigger>
))
Trigger.displayName = 'Select.Trigger'

const ScrollUpButton = React.forwardRef<
  React.ElementRef<typeof SelectPrimitive.ScrollUpButton>,
  React.ComponentPropsWithoutRef<typeof SelectPrimitive.ScrollUpButton>
>(({ className, ...props }, ref) => (
  <SelectPrimitive.ScrollUpButton
    ref={ref}
    className={cn(
      'flex cursor-default items-center justify-center py-1',
      className
    )}
    {...props}
  >
    <ChevronUp className="h-4 w-4" />
  </SelectPrimitive.ScrollUpButton>
))

const ScrollDownButton = React.forwardRef<
  React.ElementRef<typeof SelectPrimitive.ScrollDownButton>,
  React.ComponentPropsWithoutRef<typeof SelectPrimitive.ScrollDownButton>
>(({ className, ...props }, ref) => (
  <SelectPrimitive.ScrollDownButton
    ref={ref}
    className={cn(
      'flex cursor-default items-center justify-center py-1',
      className
    )}
    {...props}
  >
    <ChevronDown className="h-4 w-4" />
  </SelectPrimitive.ScrollDownButton>
))

const Content = React.forwardRef<
  React.ElementRef<typeof SelectPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof SelectPrimitive.Content>
>(({ className, children, position = 'popper', ...props }, ref) => (
  <SelectPrimitive.Content
    ref={ref}
    className={cn(
      'relative z-50 max-h-96 min-w-[8rem] overflow-hidden rounded-md bg-neutral-700 text-neutral-200 shadow-md data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 data-[side=bottom]:slide-in-from-top-2 data-[side=left]:slide-in-from-right-2 data-[side=right]:slide-in-from-left-2 data-[side=top]:slide-in-from-bottom-2',
      position === 'popper' &&
        'data-[side=bottom]:translate-y-1 data-[side=left]:-translate-x-1 data-[side=right]:translate-x-1 data-[side=top]:-translate-y-1',
      className
    )}
    position={position}
    {...props}
  >
    <ScrollUpButton />
    <SelectPrimitive.Viewport
      className={cn(
        position === 'popper' &&
          'h-[var(--radix-select-trigger-height)] w-full min-w-[var(--radix-select-trigger-width)]'
      )}
    >
      {children}
    </SelectPrimitive.Viewport>
    <ScrollDownButton />
  </SelectPrimitive.Content>
))
Content.displayName = 'Select.Content'

const Item = React.forwardRef<
  React.ElementRef<typeof SelectPrimitive.Item>,
  React.ComponentPropsWithoutRef<typeof SelectPrimitive.Item>
>(({ className, children, ...props }, ref) => (
  <SelectPrimitive.Item
    ref={ref}
    className={cn(
      'relative flex w-full h-12 cursor-default select-none items-center pl-12 pr-4 body-base outline-none focus:bg-neutral-800 data-[disabled]:pointer-events-none data-[disabled]:opacity-50',
      className
    )}
    {...props}
  >
    <SelectPrimitive.ItemIndicator className="absolute left-4">
      <Check className="h-4 w-4" />
    </SelectPrimitive.ItemIndicator>
    <SelectPrimitive.ItemText>{children}</SelectPrimitive.ItemText>
  </SelectPrimitive.Item>
))
Item.displayName = 'Select.Item'

export { Content, Item, Portal, Root, Trigger, Value }
