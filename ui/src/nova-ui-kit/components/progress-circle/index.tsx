import { cn } from 'nova-ui-kit/utils'
import { ReactNode } from 'react'
import { RADIUS_DEFAULT, RADIUS_LG, STROKE_WIDTH } from './constants'

interface ProgressCircleProps {
  children?: ReactNode
  color: string
  progress: number
  size?: 'default' | 'lg'
}

export const ProgressCircle = ({
  children,
  color,
  progress,
  size = 'default',
}: ProgressCircleProps) => {
  const radius = {
    default: RADIUS_DEFAULT,
    lg: RADIUS_LG,
  }[size]
  const normalizedRadius = radius - STROKE_WIDTH / 2
  const circumference = normalizedRadius * 2 * Math.PI
  const strokeDashoffset = circumference - progress * circumference

  return (
    <div
      className={cn('relative rounded-full')}
      style={{ width: `${radius * 2}px`, height: `${radius * 2}px` }}
    >
      <div
        className={cn(
          'w-full h-full flex items-center justify-center border-4 border-neutral-200 rounded-full text-muted-foreground'
        )}
      >
        {children}
      </div>
      <div className="absolute w-full h-full top-0 left-0">
        <svg height={radius * 2} width={radius * 2} transform="rotate(-90)">
          <circle
            className="transition-colors"
            cx={radius}
            cy={radius}
            fill="transparent"
            r={normalizedRadius}
            stroke={color}
            strokeDasharray={circumference + ' ' + circumference}
            strokeDashoffset={strokeDashoffset}
            strokeLinecap="round"
            strokeWidth={STROKE_WIDTH}
          />
        </svg>
      </div>
    </div>
  )
}
