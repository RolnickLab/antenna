import { cn } from 'nova-ui-kit/utils'
import { ReactNode } from 'react'

interface BoxProps {
  className?: string
  label?: string
  children: ReactNode
}

export const Box = ({ className, label, children }: BoxProps) => (
  <div className={cn('p-4 border border-border rounded-xl', className)}>
    {label?.length ? (
      <div className="h-8 flex items-center justify-between mx-2">
        <span className="body-overline font-bold">{label}</span>
      </div>
    ) : null}
    {children}
  </div>
)
