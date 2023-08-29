import { Icon, IconTheme, IconType } from 'design-system/components/icon/icon'
import { RADIUS, STROKE_WIDTH, THEMES } from './constants'
import styles from './identification-status.module.scss'
import { StatusTheme } from './types'

interface IdentificationStatusProps {
  iconType: IconType.Identifiers | IconType.BatchId

  theme?: StatusTheme

  /** Integer in range [0, 100] */
  value: number
}

export const IdentificationStatus = ({
  iconType = IconType.Identifiers,
  theme = StatusTheme.Success,
  value,
}: IdentificationStatusProps) => {
  const normalizedRadius = RADIUS - STROKE_WIDTH * 2
  const circumference = normalizedRadius * 2 * Math.PI
  const strokeDashoffset = circumference - (value / 100) * circumference

  return (
    <div className={styles.wrapper}>
      <div className={styles.iconWrapper}>
        <Icon type={iconType} theme={IconTheme.Primary} size={16} />
      </div>
      <svg height={RADIUS * 2} width={RADIUS * 2} transform="rotate(-90)">
        <circle
          fill="transparent"
          stroke={THEMES[theme].bg}
          strokeWidth={STROKE_WIDTH}
          r={normalizedRadius}
          cx={RADIUS}
          cy={RADIUS}
        />
        <circle
          fill="transparent"
          stroke={THEMES[theme].fg}
          strokeWidth={STROKE_WIDTH}
          strokeDasharray={circumference + ' ' + circumference}
          strokeLinecap="round"
          strokeDashoffset={strokeDashoffset}
          r={normalizedRadius}
          cx={RADIUS}
          cy={RADIUS}
        />
      </svg>
    </div>
  )
}
