import { cn } from 'design-system/utils'
import { ReactNode } from 'react'

interface IdentificationDetailsProps {
  applied?: boolean
  children?: ReactNode
  className?: string
  imageSrc?: string
}

export const IdentificationDetails = ({
  applied,
  children,
  className,
  imageSrc,
}: IdentificationDetailsProps) => (
  <div
    className={cn(
      'flex items-center justify-between',
      {
        'bg-success-50': applied,
      },
      className
    )}
  >
    <div className="flex items-center gap-4 grow py-6 px-4">{children}</div>
    {imageSrc ? <img alt="" className="h-24" src={imageSrc} /> : null}
  </div>
)
