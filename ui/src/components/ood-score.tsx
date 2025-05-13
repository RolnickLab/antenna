import { faceAlien } from '@lucide/lab'
import { Occurrence } from 'data-services/models/occurrence'
import { BasicTooltip } from 'design-system/components/tooltip/basic-tooltip'
import { Icon } from 'lucide-react'
import { CONSTANTS, ProgressCircle } from 'nova-ui-kit'
import { STRING, translate } from 'utils/language'

const OOD_SCORE_THRESHOLD = 0.3

export const OODScore = ({ occurrence }: { occurrence: Occurrence }) => {
  const color = (() => {
    if (occurrence.determinationOODScore >= OOD_SCORE_THRESHOLD) {
      return CONSTANTS.COLORS.secondary[500]
    }
    if (occurrence.determinationOODScore > 0) {
      return CONSTANTS.COLORS.neutral[500]
    }
    return CONSTANTS.COLORS.neutral[200]
  })()

  return (
    <BasicTooltip
      content={translate(STRING.OUT_OF_DISTRIBUTION_SCORE, {
        score: `${occurrence.determinationOODScore}`,
      })}
    >
      <div className="flex items-center gap-3">
        <ProgressCircle
          color={color}
          progress={occurrence.determinationOODScore}
        >
          <Icon className="w-4 h-4" iconNode={faceAlien} />
        </ProgressCircle>
        <span>{occurrence.determinationOODScoreLabel}</span>
      </div>
    </BasicTooltip>
  )
}
