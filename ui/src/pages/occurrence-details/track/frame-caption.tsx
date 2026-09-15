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
        'break-words',
        taxon ? 'text-foreground' : 'text-muted-foreground',
        { italic: !!taxon && isGenusOrBelow(taxon) }
      )}
      title={name}
    >
      {name}
    </span>
  )
}

/** Under a frame's crop: which detection and when, then the classifier's name for it, never cut off. */
export const FrameCaption = ({
  detectionId,
  label,
  timeLabel,
}: {
  detectionId: string
  label: FrameLabel
  timeLabel: string
}) => (
  <div className="flex flex-col items-center gap-0.5 text-center body-small">
    <span
      className="text-muted-foreground tabular-nums"
      title={translate(STRING.TRACK_FRAME_DETECTION, { id: detectionId })}
    >
      #{detectionId} · {timeLabel}
    </span>
    <span>
      <FrameTaxonName taxon={label.taxon} />
      {label.taxon || label.score !== undefined ? (
        <>
          {' '}
          <span className="text-foreground tabular-nums whitespace-nowrap">
            ({label.score?.toFixed(2) ?? translate(STRING.VALUE_NOT_AVAILABLE)})
          </span>
        </>
      ) : null}
    </span>
  </div>
)
