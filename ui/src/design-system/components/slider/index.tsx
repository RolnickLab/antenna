import * as SliderPrimitive from '@radix-ui/react-slider'
import { cn } from 'design-system/utils'
import * as React from 'react'

const Slider = React.forwardRef<
  React.ElementRef<typeof SliderPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof SliderPrimitive.Root> & {
    invertedColors?: boolean
  }
>(({ className, invertedColors, ...props }, ref) => (
  <SliderPrimitive.Root
    ref={ref}
    className={cn(
      'relative flex w-full touch-none select-none items-center',
      className
    )}
    {...props}
  >
    <SliderPrimitive.Track
      className={cn(
        'track relative h-2 w-full grow overflow-hidden rounded-full bg-border',
        { 'bg-primary': invertedColors }
      )}
    >
      <SliderPrimitive.Range
        className={cn('range absolute h-full bg-primary', {
          'bg-border': invertedColors,
        })}
      />
    </SliderPrimitive.Track>
    <SliderPrimitive.Thumb className="thumb block h-5 w-5 rounded-full border-2 border-primary bg-background ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50" />
  </SliderPrimitive.Root>
))
Slider.displayName = 'Slider'

export { Slider }
