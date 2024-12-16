import classNames from 'classnames'
import { Icon, IconTheme, IconType } from 'design-system/components/icon/icon'
import { forwardRef } from 'react'
import { SCORE_THRESHOLDS } from 'utils/constants'
import { RADIUS, STROKE_WIDTH, THEMES } from './constants'
import styles from './identification-status.module.scss'

interface IdentificationStatusProps {
  isVerified?: boolean

  /** Integer in range [0, 1] */
  score: number

  onStatusClick?: () => void
}

export const IdentificationStatus = forwardRef<
  HTMLDivElement,
  IdentificationStatusProps
>(({ isVerified, score, onStatusClick, ...rest }, forwardedRef) => {
  const normalizedRadius = RADIUS - STROKE_WIDTH / 2
  const circumference = normalizedRadius * 2 * Math.PI
  const strokeDashoffset = circumference - score * circumference

  const theme = (() => {
    if (score >= SCORE_THRESHOLDS.WARNING) {
      return THEMES.success
    }
    if (score >= SCORE_THRESHOLDS.ALERT) {
      return THEMES.warning
    }
    return THEMES.alert
  })()

  return (
    <div
      {...rest}
      ref={forwardedRef}
      className={classNames(styles.wrapper, {
        [styles.clickable]: !!onStatusClick,
      })}
      onClick={onStatusClick}
    >
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
  )
})
