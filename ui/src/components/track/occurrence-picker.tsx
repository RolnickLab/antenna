import classNames from 'classnames'
import {
  MergeScopeKey,
  MERGE_SCOPES,
} from 'data-services/hooks/occurrences/useMergeCandidates'
import {
  getComparisonSides,
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
import { Checkbox, LoadingSpinner, Select } from 'nova-ui-kit'
import { CSSProperties, useRef, useState } from 'react'
import { STRING, translate } from 'utils/language'
import {
  CandidateComparison,
  COMPARISON_PANEL_HEIGHT,
  COMPARISON_PANEL_WIDTH,
} from './candidate-comparison'

/** A row the picker can show. The ranking columns appear only when every row is ranked. */
export type OccurrencePickerCandidate = Pick<
  MergeCandidate,
  'id' | 'displayName' | 'images' | 'numDetections'
> &
  Partial<
    Pick<
      MergeCandidate,
      | 'relation'
      | 'timeOffsetSeconds'
      | 'distance'
      | 'similarity'
      | 'cost'
      | 'captureId'
      | 'imageTimestamp'
      | 'edgeImage'
      | 'edgeTimestamp'
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

const PANEL_GAP = 8

const headerClassName = 'px-2 py-1 font-normal text-muted-foreground'
const cellClassName = 'px-2 py-1'
const numberClassName = 'text-right tabular-nums whitespace-nowrap'
const checkboxClassName = 'w-4 h-4 accent-primary-500 cursor-pointer'

/** Beside the table when the viewport has room, otherwise clamped into view over it. */
const getPanelStyle = (
  table: DOMRect | undefined,
  row: DOMRect
): CSSProperties => {
  const maxLeft = window.innerWidth - COMPARISON_PANEL_WIDTH - PANEL_GAP
  const maxTop = window.innerHeight - COMPARISON_PANEL_HEIGHT - PANEL_GAP
  let left = table ? table.right + PANEL_GAP : maxLeft

  if (left > maxLeft && table) {
    left = table.left - PANEL_GAP - COMPARISON_PANEL_WIDTH
  }

  return {
    left: Math.max(PANEL_GAP, Math.min(left, maxLeft)),
    top: Math.max(PANEL_GAP, Math.min(row.top, maxTop)),
  }
}

export const OccurrencePicker = ({
  candidates,
  description = translate(STRING.TRACK_PICK_OCCURRENCE_SCOPE),
  emptyMessage = translate(STRING.TRACK_NO_OTHER_OCCURRENCES),
  isLoading,
  onScopeChange,
  onSelect,
  onShowOverlappingChange,
  onToggle,
  overlappingCount,
  scope,
  selectedId,
  selectedIds = [],
  showOverlapping = false,
  title = translate(STRING.TRACK_PICK_OCCURRENCE),
}: {
  candidates: OccurrencePickerCandidate[]
  description?: string
  emptyMessage?: string
  isLoading?: boolean
  onScopeChange?: (key: MergeScopeKey) => void
  /** Single-select: clicking a row makes it the one selection. */
  onSelect?: (id: string) => void
  onShowOverlappingChange?: (value: boolean) => void
  /** Multi-select: rows get checkboxes. Select-all calls this once per row, so update state functionally. */
  onToggle?: (id: string) => void
  overlappingCount?: number
  scope?: MergeScopeKey
  selectedId?: string
  selectedIds?: string[]
  showOverlapping?: boolean
  title?: string
}) => {
  const [sort, setSort] = useState<MergeCandidateSort>()
  const [hovered, setHovered] = useState<{
    candidate: MergeCandidate
    style: CSSProperties
  }>()
  const tableRef = useRef<HTMLDivElement>(null)

  const multi = !!onToggle
  const ranked = isRanked(candidates)
  const rows = ranked ? sortMergeCandidates(candidates, sort) : candidates
  const numSelectedShown = rows.filter((row) =>
    selectedIds.includes(row.id)
  ).length

  const toggleSort = (column: MergeCandidateSortColumn) =>
    setSort(
      sort?.column === column
        ? { column, descending: !sort.descending }
        : { column, descending: DESCENDING_FIRST.includes(column) }
    )

  const pick = (id: string) => (multi ? onToggle?.(id) : onSelect?.(id))

  const toggleAll = () =>
    rows
      .filter((row) =>
        numSelectedShown === rows.length
          ? selectedIds.includes(row.id)
          : !selectedIds.includes(row.id)
      )
      .forEach((row) => onToggle?.(row.id))

  const showComparison = (
    candidate: OccurrencePickerCandidate,
    row: HTMLElement
  ) => {
    if (!ranked || !candidate.images[0]) {
      return
    }

    setHovered({
      candidate: candidate as MergeCandidate,
      style: getPanelStyle(
        tableRef.current?.getBoundingClientRect(),
        row.getBoundingClientRect()
      ),
    })
  }

  const hideComparison = () => setHovered(undefined)

  const hasControls =
    (scope && onScopeChange) ||
    (overlappingCount !== undefined && onShowOverlappingChange)

  return (
    <div className="flex flex-col gap-1">
      <span className="body-small">{title}</span>
      <span className="body-small text-muted-foreground">{description}</span>
      {hasControls ? (
        <div className="flex flex-wrap items-center gap-4 py-1">
          {scope && onScopeChange ? (
            <Select.Root
              value={scope}
              onValueChange={(value) => onScopeChange(value as MergeScopeKey)}
            >
              <Select.Trigger
                aria-label={translate(STRING.TRACK_SCOPE_LABEL)}
                className="h-8 w-auto gap-2 px-3 body-small text-foreground"
              >
                <Select.Value />
              </Select.Trigger>
              <Select.Content>
                {MERGE_SCOPES.map((option) => (
                  <Select.Item
                    className="h-8 body-small"
                    key={option.key}
                    value={option.key}
                  >
                    {translate(option.label)}
                  </Select.Item>
                ))}
              </Select.Content>
            </Select.Root>
          ) : null}
          {overlappingCount !== undefined && onShowOverlappingChange ? (
            <Checkbox
              checked={showOverlapping}
              id="occurrence-picker-overlapping"
              label={translate(STRING.TRACK_SHOW_OVERLAPPING, {
                count: overlappingCount,
              })}
              onCheckedChange={onShowOverlappingChange}
            />
          ) : null}
        </div>
      ) : null}
      {isLoading ? (
        <div className="flex justify-center py-6">
          <LoadingSpinner size={24} />
        </div>
      ) : !candidates.length ? (
        <span className="body-small text-muted-foreground">{emptyMessage}</span>
      ) : (
        <div
          className="max-h-64 overflow-y-auto"
          onMouseLeave={hideComparison}
          onScroll={hideComparison}
          ref={tableRef}
        >
          <table className="w-full body-small text-left border-collapse">
            <thead className="sticky top-0 bg-background">
              <tr>
                {multi ? (
                  <th className={classNames(headerClassName, 'w-6')}>
                    <input
                      aria-label={translate(STRING.TRACK_SELECT_ALL)}
                      checked={
                        numSelectedShown > 0 && numSelectedShown === rows.length
                      }
                      className={checkboxClassName}
                      onChange={toggleAll}
                      ref={(input) => {
                        if (input) {
                          input.indeterminate =
                            numSelectedShown > 0 &&
                            numSelectedShown < rows.length
                        }
                      }}
                      type="checkbox"
                    />
                  </th>
                ) : null}
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
                const selected = multi
                  ? selectedIds.includes(candidate.id)
                  : candidate.id === selectedId
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
                    onClick={() => pick(candidate.id)}
                    onMouseEnter={(e) =>
                      showComparison(candidate, e.currentTarget)
                    }
                  >
                    {multi ? (
                      <td
                        className={classNames(cellClassName, 'w-6')}
                        onClick={(e) => e.stopPropagation()}
                      >
                        <input
                          aria-label={translate(STRING.TRACK_SELECT_ROW, {
                            name: candidate.displayName,
                          })}
                          checked={selected}
                          className={checkboxClassName}
                          onChange={() => onToggle?.(candidate.id)}
                          type="checkbox"
                        />
                      </td>
                    ) : null}
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
                        onBlur={hideComparison}
                        onClick={(e) => {
                          e.stopPropagation()
                          pick(candidate.id)
                        }}
                        onFocus={(e) =>
                          showComparison(
                            candidate,
                            e.currentTarget.closest('tr') ?? e.currentTarget
                          )
                        }
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
      )}
      {hovered ? (
        <CandidateComparison
          displayName={hovered.candidate.displayName}
          sides={getComparisonSides(hovered.candidate)}
          style={hovered.style}
        />
      ) : null}
    </div>
  )
}
