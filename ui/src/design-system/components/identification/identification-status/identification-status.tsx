import { Icon, IconTheme, IconType } from 'design-system/components/icon/icon'
import { RADIUS, STROKE_WIDTH, THEMES } from './constants'
import styles from './identification-status.module.scss'

interface IdentificationStatusProps {
  isVerified?: boolean

  /** Integer in range [0, 1] */
  score: number

  /** Integer in range [0, 1] */
  scoreThreshold?: number
}

export const IdentificationStatus = ({
  isVerified,
  scoreThreshold = 0.6,
  score,
}: IdentificationStatusProps) => {
  const normalizedRadius = RADIUS - STROKE_WIDTH * 2
  const circumference = normalizedRadius * 2 * Math.PI
  const strokeDashoffset = circumference - score * circumference
  const theme = score >= scoreThreshold ? THEMES.success : THEMES.alert

  return (
    <div className={styles.wrapper}>
      <div className={styles.iconWrapper}>
        <Icon
          type={isVerified ? IconType.Identifiers : IconType.BatchId}
          theme={IconTheme.Primary}
          size={16}
        />
      </div>
      <svg height={RADIUS * 2} width={RADIUS * 2} transform="rotate(-90)">
        <circle
          fill="transparent"
          stroke={theme.bg}
          strokeWidth={STROKE_WIDTH}
          r={normalizedRadius}
          cx={RADIUS}
          cy={RADIUS}
        />
        <circle
          fill="transparent"
          stroke={theme.fg}
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
