import classNames from 'classnames'
import { Occurrence } from 'data-services/models/occurrence'
import { LoadingSpinner } from 'nova-ui-kit'
import { STRING, translate } from 'utils/language'

export const OccurrencePicker = ({
  candidates,
  isLoading,
  onSelect,
  selectedId,
}: {
  candidates: Occurrence[]
  isLoading?: boolean
  onSelect: (id: string) => void
  selectedId?: string
}) => {
  if (isLoading) {
    return (
      <div className="flex justify-center py-6">
        <LoadingSpinner size={24} />
      </div>
    )
  }

  if (!candidates.length) {
    return (
      <span className="body-small text-muted-foreground">
        {translate(STRING.TRACK_NO_OTHER_OCCURRENCES)}
      </span>
    )
  }

  return (
    <div className="flex flex-col gap-1 max-h-64 overflow-y-auto">
      <span className="body-small">
        {translate(STRING.TRACK_PICK_OCCURRENCE)}
      </span>
      <span className="body-small text-muted-foreground">
        {translate(STRING.TRACK_PICK_OCCURRENCE_SCOPE)}
      </span>
      {candidates.map((candidate) => (
        <button
          aria-pressed={candidate.id === selectedId}
          className={classNames(
            'flex items-center gap-3 p-2 rounded-md text-left',
            candidate.id === selectedId
              ? 'bg-primary-100 ring-1 ring-primary-500'
              : 'hover:bg-muted'
          )}
          key={candidate.id}
          onClick={() => onSelect(candidate.id)}
          type="button"
        >
          {candidate.images[0] ? (
            <img
              alt=""
              className="w-10 h-10 object-contain shrink-0"
              onError={(e) => (e.currentTarget.hidden = true)}
              src={candidate.images[0].src}
            />
          ) : null}
          <span className="flex flex-col">
            <span className="body-small">{candidate.displayName}</span>
            <span className="body-small text-muted-foreground">
              {candidate.timeLabel} · {candidate.numDetections} ·{' '}
              {candidate.durationLabel ?? translate(STRING.VALUE_NOT_AVAILABLE)}
            </span>
          </span>
        </button>
      ))}
    </div>
  )
}
