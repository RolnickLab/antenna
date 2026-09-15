import { isGenusOrBelow } from 'components/taxon-details/utils'
import { FrameLabel } from 'data-services/models/occurrence-details'
import { Taxon } from 'data-services/models/taxa'
import { cn } from 'nova-ui-kit/utils'
import { STRING, translate } from 'utils/language'

export const FrameTaxonName = ({ taxon }: { taxon?: Taxon }) => {
  const name = taxon?.name ?? translate(STRING.TRACK_FRAME_NO_CLASSIFICATION)

  return (
    <span
      className={cn(
        'truncate',
        taxon ? 'text-foreground' : 'text-muted-foreground',
        { italic: !!taxon && isGenusOrBelow(taxon) }
      )}
      title={name}
    >
      {name}
    </span>
  )
}

export const FrameCaption = ({
  detectionId,
  label,
}: {
  detectionId: string
  label: FrameLabel
}) => (
  <div className="flex items-center justify-end gap-1.5 min-w-0 body-small">
    <FrameTaxonName taxon={label.taxon} />
    <span className="shrink-0 text-foreground tabular-nums">
      {label.score?.toFixed(2) ?? translate(STRING.VALUE_NOT_AVAILABLE)}
    </span>
    <span
      className="shrink-0 text-muted-foreground"
      title={translate(STRING.TRACK_FRAME_DETECTION, { id: detectionId })}
    >
      #{detectionId}
    </span>
  </div>
)
