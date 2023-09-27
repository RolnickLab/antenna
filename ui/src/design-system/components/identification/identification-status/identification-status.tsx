import { Icon, IconTheme, IconType } from 'design-system/components/icon/icon'
import { Tooltip } from 'design-system/components/tooltip/tooltip'
import _ from 'lodash'
import { RADIUS, STROKE_WIDTH, THEMES } from './constants'
import styles from './identification-status.module.scss'

interface IdentificationStatusProps {
  /** Integer in range [0, 1] */
  alertThreshold?: number

  isVerified?: boolean

  /** Integer in range [0, 1] */
  score: number

  /** Integer in range [0, 1] */
  warningThreshold?: number
}

export const IdentificationStatus = ({
  alertThreshold = 0.7,
  isVerified,
  score,
  warningThreshold = 0.9,
}: IdentificationStatusProps) => {
  const normalizedRadius = RADIUS - STROKE_WIDTH / 2
  const circumference = normalizedRadius * 2 * Math.PI
  const strokeDashoffset = circumference - score * circumference

  const theme = (() => {
    if (score >= warningThreshold) {
      return THEMES.success
    }
    if (score >= alertThreshold) {
      return THEMES.warning
    }
    return THEMES.alert
  })()

  const tooltipContent = isVerified
    ? 'Verified by human'
    : `Machine prediction\nscore ${_.round(score, 4)}`

  return (
    <Tooltip content={tooltipContent}>
      <div className={styles.wrapper}>
        <div className={styles.iconWrapper}>
          <Icon
            type={isVerified ? IconType.ShieldCheck : IconType.BatchId}
            theme={IconTheme.Primary}
            size={14}
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
    </Tooltip>
  )
}
