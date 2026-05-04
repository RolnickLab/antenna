import { BasicTooltip } from 'design-system/components/tooltip/basic-tooltip'
import { IdentificationScore } from 'nova-ui-kit'
import { STRING, translate } from 'utils/language'

export const DeterminationScore = ({
  score,
  scoreLabel,
  tooltip,
  verified,
}: {
  score?: number
  scoreLabel?: string
  tooltip?: string
  verified?: boolean
}) => {
  if (score === undefined || scoreLabel === undefined) {
    return <span>{translate(STRING.VALUE_NOT_AVAILABLE)}</span>
  }

  return (
    <BasicTooltip content={tooltip}>
      <div className="flex items-center gap-3">
        <IdentificationScore confirmed={verified} confidenceScore={score} />
        <span>{verified ? translate(STRING.VERIFIED) : scoreLabel}</span>
      </div>
    </BasicTooltip>
  )
}
