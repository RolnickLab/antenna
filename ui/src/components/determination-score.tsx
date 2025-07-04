import { BasicTooltip } from 'design-system/components/tooltip/basic-tooltip'
import { IdentificationScore } from 'nova-ui-kit'
import { STRING, translate } from 'utils/language'

export const DeterminationScore = ({
  confirmed,
  score,
  scoreLabel,
  tooltip,
}: {
  confirmed?: boolean
  score?: number
  scoreLabel?: string
  tooltip?: string
}) => {
  if (score === undefined || scoreLabel === undefined) {
    return <span>{translate(STRING.VALUE_NOT_AVAILABLE)}</span>
  }

  return (
    <BasicTooltip content={tooltip}>
      <div className="flex items-center gap-3">
        <IdentificationScore confirmed={confirmed} confidenceScore={score} />
        <span>{scoreLabel}</span>
      </div>
    </BasicTooltip>
  )
}
