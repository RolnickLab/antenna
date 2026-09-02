import { EyeIcon, ShieldCheckIcon } from 'lucide-react'
import { CONSTANTS } from 'nova-ui-kit/constants'
import { ProgressCircle } from '../progress-circle'
import { RADIUS_DEFAULT, RADIUS_LG } from '../progress-circle/constants'

interface IdentificationScoreProps {
  confidenceScore: number
  confidenceScoreThresholds?: { warning: number; alert: number }
  confirmed?: boolean
  size?: 'default' | 'lg'
}

export const IdentificationScore = ({
  confidenceScore,
  confidenceScoreThresholds = {
    warning: 0.8,
    alert: 0.6,
  },
  confirmed,
  size = 'default',
}: IdentificationScoreProps) => {
  const color = (() => {
    if (confidenceScore >= confidenceScoreThresholds.warning) {
      return CONSTANTS.COLORS.success[500]
    }
    if (confidenceScore >= confidenceScoreThresholds.alert) {
      return CONSTANTS.COLORS.warning[500]
    }
    return CONSTANTS.COLORS.alert[600]
  })()

  const Icon = confirmed ? ShieldCheckIcon : EyeIcon

  const iconSize = {
    default: RADIUS_DEFAULT,
    lg: RADIUS_LG,
  }[size]

  return (
    <ProgressCircle color={color} progress={confidenceScore} size={size}>
      <Icon style={{ width: `${iconSize}px`, height: `${iconSize}px` }} />
    </ProgressCircle>
  )
}
