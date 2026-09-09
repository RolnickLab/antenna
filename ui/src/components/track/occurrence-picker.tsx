import classNames from 'classnames'
import {
  getDistanceLabel,
  getSimilarityLabel,
  getWhenLabel,
  MergeCandidate,
  MergeCandidateSort,
  MergeCandidateSortColumn,
  sortMergeCandidates,
} from 'data-services/models/merge-candidate'
import {
  ArrowDownIcon,
  ArrowLeftIcon,
  ArrowLeftRightIcon,
  ArrowRightIcon,
  ArrowUpDownIcon,
  ArrowUpIcon,
} from 'lucide-react'
import { LoadingSpinner } from 'nova-ui-kit'
import { useState } from 'react'
import { STRING, translate } from 'utils/language'

/** A row the picker can show. The ranking columns appear only when every row is ranked. */
export type OccurrencePickerCandidate = Pick<
  MergeCandidate,
  'id' | 'displayName' | 'images' | 'numDetections'
> &
  Partial<
    Pick<
      MergeCandidate,
      'relation' | 'timeOffsetSeconds' | 'distance' | 'similarity' | 'cost'
    >
  >

const isRanked = (
  candidates: OccurrencePickerCandidate[]
): candidates is MergeCandidate[] =>
  candidates.length > 0 &&
  candidates.every((candidate) => candidate.relation !== undefined)

// The first click on a column gives its natural order: earliest first, closest
// first, or most alike first.
const DESCENDING_FIRST: MergeCandidateSortColumn[] = ['similarity']

const RELATION_ICONS = {
  before: ArrowLeftIcon,
  after: ArrowRightIcon,
  overlapping: ArrowLeftRightIcon,
}

const SORT_COLUMNS: { column: MergeCandidateSortColumn; label: STRING }[] = [
  { column: 'when', label: STRING.TRACK_COLUMN_WHEN },
  { column: 'distance', label: STRING.TRACK_COLUMN_DISTANCE },
  { column: 'similarity', label: STRING.TRACK_COLUMN_SIMILARITY },
]

const headerClassName = 'px-2 py-1 font-normal text-muted-foreground'
const cellClassName = 'px-2 py-1'
const numberClassName = 'text-right tabular-nums whitespace-nowrap'

export const OccurrencePicker = ({
  candidates,
  description = translate(STRING.TRACK_PICK_OCCURRENCE_SCOPE),
  emptyMessage = translate(STRING.TRACK_NO_OTHER_OCCURRENCES),
  isLoading,
  onSelect,
  selectedId,
  title = translate(STRING.TRACK_PICK_OCCURRENCE),
}: {
  candidates: OccurrencePickerCandidate[]
  description?: string
  emptyMessage?: string
  isLoading?: boolean
  onSelect: (id: string) => void
  selectedId?: string
  title?: string
}) => {
  const [sort, setSort] = useState<MergeCandidateSort>()

  if (isLoading) {
    return (
      <div className="flex justify-center py-6">
        <LoadingSpinner size={24} />
      </div>
    )
  }

  if (!candidates.length) {
    return (
      <span className="body-small text-muted-foreground">{emptyMessage}</span>
    )
  }

  const ranked = isRanked(candidates)
  const rows = ranked ? sortMergeCandidates(candidates, sort) : candidates

  const toggleSort = (column: MergeCandidateSortColumn) =>
    setSort(
      sort?.column === column
        ? { column, descending: !sort.descending }
        : { column, descending: DESCENDING_FIRST.includes(column) }
    )

  return (
    <div className="flex flex-col gap-1">
      <span className="body-small">{title}</span>
      <span className="body-small text-muted-foreground">{description}</span>
      <div className="max-h-64 overflow-y-auto">
        <table className="w-full body-small text-left border-collapse">
          <thead className="sticky top-0 bg-background">
            <tr>
              <th className={headerClassName}>
                <span className="sr-only">
                  {translate(STRING.TRACK_COLUMN_IMAGE)}
                </span>
              </th>
              <th className={headerClassName}>
                {translate(STRING.TRACK_COLUMN_SPECIES)}
              </th>
              <th className={classNames(headerClassName, numberClassName)}>
                {translate(STRING.TRACK_COLUMN_FRAMES)}
              </th>
              {ranked &&
                SORT_COLUMNS.map(({ column, label }) => {
                  const active = sort?.column === column
                  const DirectionIcon = !active
                    ? ArrowUpDownIcon
                    : sort.descending
                    ? ArrowDownIcon
                    : ArrowUpIcon

                  return (
                    <th
                      aria-sort={
                        active
                          ? sort.descending
                            ? 'descending'
                            : 'ascending'
                          : 'none'
                      }
                      className={classNames(headerClassName, numberClassName)}
                      key={column}
                    >
                      <button
                        aria-label={translate(STRING.TRACK_SORT_BY, {
                          column: translate(label),
                        })}
                        className={classNames(
                          'inline-flex items-center gap-1 hover:text-foreground',
                          { 'text-foreground': active }
                        )}
                        onClick={() => toggleSort(column)}
                        type="button"
                      >
                        <span>{translate(label)}</span>
                        <DirectionIcon aria-hidden className="w-3 h-3" />
                      </button>
                    </th>
                  )
                })}
            </tr>
          </thead>
          <tbody>
            {rows.map((candidate) => {
              const selected = candidate.id === selectedId
              const RelationIcon = candidate.relation
                ? RELATION_ICONS[candidate.relation]
                : undefined

              return (
                <tr
                  aria-selected={selected}
                  className={classNames(
                    'cursor-pointer',
                    selected
                      ? 'bg-primary-100 ring-1 ring-inset ring-primary-500'
                      : 'hover:bg-muted'
                  )}
                  key={candidate.id}
                  onClick={() => onSelect(candidate.id)}
                >
                  <td className={classNames(cellClassName, 'w-10')}>
                    {candidate.images[0] ? (
                      <img
                        alt=""
                        className="w-8 h-8 object-contain"
                        onError={(e) => (e.currentTarget.hidden = true)}
                        src={candidate.images[0].src}
                      />
                    ) : null}
                  </td>
                  <td className={cellClassName}>
                    <button
                      aria-pressed={selected}
                      className="text-left"
                      onClick={() => onSelect(candidate.id)}
                      type="button"
                    >
                      {candidate.displayName}
                    </button>
                  </td>
                  <td className={classNames(cellClassName, numberClassName)}>
                    {candidate.numDetections}
                  </td>
                  {ranked && candidate.relation !== undefined ? (
                    <>
                      <td
                        className={classNames(cellClassName, numberClassName)}
                      >
                        <span className="inline-flex items-center gap-1">
                          {RelationIcon ? (
                            <RelationIcon
                              aria-hidden
                              className="w-3 h-3 text-muted-foreground"
                            />
                          ) : null}
                          <span>
                            {getWhenLabel(
                              candidate.relation,
                              candidate.timeOffsetSeconds ?? 0
                            )}
                          </span>
                        </span>
                      </td>
                      <td
                        className={classNames(cellClassName, numberClassName)}
                      >
                        {getDistanceLabel(candidate.distance ?? null)}
                      </td>
                      <td
                        className={classNames(cellClassName, numberClassName)}
                      >
                        {getSimilarityLabel(candidate.similarity ?? null)}
                      </td>
                    </>
                  ) : null}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
