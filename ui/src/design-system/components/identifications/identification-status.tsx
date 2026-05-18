import { CONSTANTS } from 'design-system/constants'
import { cn } from 'design-system/utils'
import { ProgressCircle } from '../progress-circle'

interface IdentificationStatusProps {
  applied?: boolean
  confidenceScore: number
  confidenceScoreThresholds?: { warning: number; alert: number }
}

export const IdentificationStatus = ({
  applied,
  confidenceScore,
  confidenceScoreThresholds = {
    warning: 0.8,
    alert: 0.6,
  },
}: IdentificationStatusProps) => {
  const color = (() => {
    if (confidenceScore >= confidenceScoreThresholds.warning) {
      return CONSTANTS.COLORS.success[500]
    }
    if (confidenceScore >= confidenceScoreThresholds.alert) {
      return CONSTANTS.COLORS.warning[500]
    }
    return CONSTANTS.COLORS.alert[600]
  })()

  return (
    <ProgressCircle color={color} progress={confidenceScore} size="lg">
      <div
        className={cn(
          'bg-primary-300 border-4 border-neutral-200 rounded-full text-generic-white',
          { 'bg-success-300 text-success-50': applied }
        )}
      >
        <CheckIcon />
      </div>
    </ProgressCircle>
  )
}

const CheckIcon = () => (
  <svg
    fill="none"
    height="32"
    viewBox="0 0 32 32"
    width="32"
    xmlns="http://www.w3.org/2000/svg"
  >
    <path
      clipRule="evenodd"
      d="M23.4142 13.4142C24.1953 12.6332 24.1953 11.3668 23.4142 10.5858C22.6332 9.80474 21.3668 9.80474 20.5858 10.5858L14 17.1716L11.4142 14.5858C10.6332 13.8047 9.36683 13.8047 8.58579 14.5858C7.80474 15.3668 7.80474 16.6332 8.58579 17.4142L12.5858 21.4142C13.3668 22.1953 14.6332 22.1953 15.4142 21.4142L23.4142 13.4142Z"
      fill="currentColor"
      fillRule="evenodd"
    />
  </svg>
)
