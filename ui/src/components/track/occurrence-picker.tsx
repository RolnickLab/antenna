import classNames from 'classnames'
import {
  MergeScopeKey,
  MERGE_SCOPES,
} from 'data-services/hooks/occurrences/useMergeCandidates'
import {
  getComparisonSides,
  getCostLabel,
  getDistanceLabel,
  getRatioLabel,
  getSimilarityLabel,
  getWhenLabel,
  getWhenOffsetSeconds,
  MergeCandidate,
  MergeCandidateSort,
  MergeCandidateSortColumn,
  sortMergeCandidates,
} from 'data-services/models/merge-candidate'
import {
  ArrowDownIcon,
  ArrowLeftIcon,
  ArrowRightIcon,
  ArrowUpDownIcon,
  ArrowUpIcon,
  CheckIcon,
  ExternalLinkIcon,
} from 'lucide-react'
import { BasicTooltip, LoadingSpinner, Select } from 'nova-ui-kit'
import { CSSProperties, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
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
      | 'iou'
      | 'sizeRatio'
      | 'likelihood'
      | 'cost'
      | 'wouldLink'
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
const DESCENDING_FIRST: MergeCandidateSortColumn[] = ['similarity', 'match']

const COLUMN_LABELS: Record<MergeCandidateSortColumn, STRING> = {
  when: STRING.TRACK_COLUMN_WHEN,
  distance: STRING.TRACK_COLUMN_DISTANCE,
  similarity: STRING.TRACK_COLUMN_SIMILARITY,
  cost: STRING.TRACK_COLUMN_COST,
  match: STRING.TRACK_COLUMN_MATCH,
}

// Cost and the percentage derived from it rank rows differently, so each says what it is.
const COLUMN_HELP: Partial<Record<MergeCandidateSortColumn, STRING>> = {
  cost: STRING.TRACK_COLUMN_COST_HELP,
  match: STRING.TRACK_COLUMN_MATCH_HELP,
}

const SORT_COLUMNS: MergeCandidateSortColumn[] = [
  'when',
  'distance',
  'similarity',
  'cost',
  'match',
]

const BEST_MATCH = 'best'
const CUMULATIVE = 'cumulative'

const PANEL_GAP = 8

const headerClassName = 'px-2 py-1 font-normal text-muted-foreground'
const cellClassName = 'px-2 py-1'
const numberClassName = 'text-right tabular-nums whitespace-nowrap'
const checkboxClassName = 'w-4 h-4 accent-primary-500 cursor-pointer'

/**
 * Beside the table when the viewport has room. Otherwise over the table's far side,
 * below or above the row, so it never hides the first column's checkboxes.
 */
const getPanelStyle = (
  table: DOMRect | undefined,
  row: HTMLElement
): CSSProperties | undefined => {
  const rowRect = row.getBoundingClientRect()
  const maxLeft = window.innerWidth - COMPARISON_PANEL_WIDTH - PANEL_GAP
  const maxTop = window.innerHeight - COMPARISON_PANEL_HEIGHT - PANEL_GAP
  const besideTop = Math.max(PANEL_GAP, Math.min(rowRect.top, maxTop))

  if (!table) {
    return { left: maxLeft, top: besideTop }
  }
  if (table.right + PANEL_GAP <= maxLeft) {
    return { left: table.right + PANEL_GAP, top: besideTop }
  }
  if (table.left - PANEL_GAP - COMPARISON_PANEL_WIDTH >= PANEL_GAP) {
    return {
      left: table.left - PANEL_GAP - COMPARISON_PANEL_WIDTH,
      top: besideTop,
    }
  }

  const clearOf =
    (row.firstElementChild ?? row).getBoundingClientRect().right + PANEL_GAP
  const left = Math.min(
    Math.max(table.right - COMPARISON_PANEL_WIDTH, clearOf),
    maxLeft
  )
  if (left < clearOf) {
    // Too narrow to show it without covering the first column.
    return undefined
  }

  const below = rowRect.bottom + PANEL_GAP
  const above = rowRect.top - PANEL_GAP - COMPARISON_PANEL_HEIGHT
  const top = below <= maxTop ? below : above >= PANEL_GAP ? above : besideTop

  return { left, top }
}

export const OccurrencePicker = ({
  candidates,
  costThreshold,
  description = translate(STRING.TRACK_PICK_OCCURRENCE_SCOPE),
  emptyMessage = translate(STRING.TRACK_NO_OTHER_OCCURRENCES),
  isLoading,
  onScopeChange,
  onSelect,
  onToggle,
  requiresFeatures,
  scope,
  selectedId,
  selectedIds = [],
  sessionLink,
  title = translate(STRING.TRACK_PICK_OCCURRENCE),
}: {
  candidates: OccurrencePickerCandidate[]
  /** Tracking links a pair only under this cost; shown beside each cost in the preview. */
  costThreshold?: number
  description?: string
  emptyMessage?: string
  isLoading?: boolean
  onScopeChange?: (key: MergeScopeKey) => void
  /** Single-select: clicking a row makes it the one selection. */
  onSelect?: (id: string) => void
  /** Multi-select: rows get checkboxes. Select-all calls this once per row, so update state functionally. */
  onToggle?: (id: string) => void
  /** Tracking skips a pair with no vector on both sides instead of matching it on geometry. */
  requiresFeatures?: boolean
  scope?: MergeScopeKey
  selectedId?: string
  selectedIds?: string[]
  /** Where to open a candidate in its session; rows get a link when this returns a route. */
  sessionLink?: (candidate: MergeCandidate) => string | undefined
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

  const columnSort = sort && 'column' in sort ? sort : undefined

  const toggleSort = (column: MergeCandidateSortColumn) =>
    setSort(
      columnSort?.column === column
        ? { column, descending: !columnSort.descending }
        : { column, descending: DESCENDING_FIRST.includes(column) }
    )

  const chooseOrder = (value: string) =>
    setSort(value === CUMULATIVE ? { cumulative: true } : undefined)

  const pick = (candidate: OccurrencePickerCandidate) =>
    multi ? onToggle?.(candidate.id) : onSelect?.(candidate.id)

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

    const style = getPanelStyle(tableRef.current?.getBoundingClientRect(), row)
    setHovered(
      style ? { candidate: candidate as MergeCandidate, style } : undefined
    )
  }

  const hideComparison = () => setHovered(undefined)

  return (
    <div className="flex flex-col gap-1">
      <span className="body-small">{title}</span>
      <span className="body-small text-muted-foreground">{description}</span>
      {(scope && onScopeChange) || ranked ? (
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
          {ranked ? (
            <Select.Root
              value={columnSort?.column ?? (sort ? CUMULATIVE : BEST_MATCH)}
              onValueChange={chooseOrder}
            >
              <Select.Trigger
                aria-label={translate(STRING.TRACK_SORT_LABEL)}
                className="h-8 w-auto gap-2 px-3 body-small text-foreground"
              >
                <Select.Value />
              </Select.Trigger>
              <Select.Content>
                <Select.Item className="h-8 body-small" value={BEST_MATCH}>
                  {translate(STRING.TRACK_SORT_BEST)}
                </Select.Item>
                <Select.Item className="h-8 body-small" value={CUMULATIVE}>
                  {translate(STRING.TRACK_SORT_CUMULATIVE)}
                </Select.Item>
                {/* Named so the control still reads true after a column header sets the order. */}
                {columnSort ? (
                  <Select.Item
                    className="h-8 body-small"
                    value={columnSort.column}
                  >
                    {translate(COLUMN_LABELS[columnSort.column])}
                  </Select.Item>
                ) : null}
              </Select.Content>
            </Select.Root>
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
                  SORT_COLUMNS.map((column) => {
                    const label = COLUMN_LABELS[column]
                    const help = COLUMN_HELP[column]
                    const active = columnSort?.column === column
                    const DirectionIcon = !active
                      ? ArrowUpDownIcon
                      : columnSort.descending
                      ? ArrowDownIcon
                      : ArrowUpIcon

                    return (
                      <th
                        aria-sort={
                          active
                            ? columnSort.descending
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
                          {help ? (
                            <BasicTooltip asChild content={translate(help)}>
                              <span className="underline decoration-dotted underline-offset-2">
                                {translate(label)}
                              </span>
                            </BasicTooltip>
                          ) : (
                            <span>{translate(label)}</span>
                          )}
                          <DirectionIcon aria-hidden className="w-3 h-3" />
                        </button>
                      </th>
                    )
                  })}
                {ranked && sessionLink ? (
                  <th className={classNames(headerClassName, 'w-8')}>
                    <span className="sr-only">
                      {translate(STRING.VIEW_IN_SESSION)}
                    </span>
                  </th>
                ) : null}
              </tr>
            </thead>
            <tbody>
              {rows.map((candidate) => {
                const selected = multi
                  ? selectedIds.includes(candidate.id)
                  : candidate.id === selectedId
                const whenOffset =
                  candidate.relation !== undefined
                    ? getWhenOffsetSeconds(candidate as MergeCandidate)
                    : undefined
                const RelationIcon =
                  whenOffset === undefined
                    ? undefined
                    : whenOffset < 0
                    ? ArrowLeftIcon
                    : ArrowRightIcon
                const whenLabel = (
                  <span className="inline-flex items-center gap-1">
                    {RelationIcon ? (
                      <RelationIcon
                        aria-hidden
                        className="w-3 h-3 text-muted-foreground"
                      />
                    ) : null}
                    <span>
                      {whenOffset !== undefined
                        ? getWhenLabel(whenOffset)
                        : null}
                    </span>
                  </span>
                )

                return (
                  <tr
                    aria-selected={selected}
                    className={classNames(
                      selected
                        ? 'cursor-pointer bg-primary-100 ring-1 ring-inset ring-primary-500'
                        : 'cursor-pointer hover:bg-muted'
                    )}
                    key={candidate.id}
                    onClick={() => pick(candidate)}
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
                          onChange={() => pick(candidate)}
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
                          pick(candidate)
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
                          {candidate.relation === 'gap' ? (
                            <BasicTooltip
                              asChild
                              content={translate(STRING.TRACK_CANDIDATE_IN_GAP)}
                            >
                              {whenLabel}
                            </BasicTooltip>
                          ) : (
                            whenLabel
                          )}
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
                        <td
                          className={classNames(cellClassName, numberClassName)}
                        >
                          {getCostLabel(candidate.cost ?? null)}
                        </td>
                        <td
                          className={classNames(cellClassName, numberClassName)}
                        >
                          <span className="inline-flex items-center justify-end gap-1">
                            {candidate.wouldLink ? (
                              <BasicTooltip
                                asChild
                                content={translate(
                                  STRING.TRACK_MATCH_WOULD_LINK
                                )}
                              >
                                <CheckIcon
                                  aria-label={translate(
                                    STRING.TRACK_MATCH_WOULD_LINK
                                  )}
                                  className="w-3 h-3 text-success"
                                  role="img"
                                />
                              </BasicTooltip>
                            ) : null}
                            <span>
                              {getRatioLabel(candidate.likelihood ?? null)}
                            </span>
                          </span>
                        </td>
                        {sessionLink ? (
                          <td className={classNames(cellClassName, 'w-8')}>
                            {(() => {
                              const route = sessionLink(
                                candidate as MergeCandidate
                              )

                              return route ? (
                                <Link
                                  aria-label={translate(
                                    STRING.TRACK_VIEW_CANDIDATE_IN_SESSION,
                                    { name: candidate.displayName }
                                  )}
                                  className="inline-flex text-muted-foreground hover:text-foreground"
                                  onClick={(e) => e.stopPropagation()}
                                  rel="noreferrer"
                                  target="_blank"
                                  title={translate(STRING.VIEW_IN_SESSION)}
                                  to={route}
                                >
                                  <ExternalLinkIcon
                                    aria-hidden
                                    className="w-3.5 h-3.5"
                                  />
                                </Link>
                              ) : null
                            })()}
                          </td>
                        ) : null}
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
          candidate={hovered.candidate}
          costThreshold={costThreshold}
          requiresFeatures={requiresFeatures}
          sides={getComparisonSides(hovered.candidate)}
          style={hovered.style}
        />
      ) : null}
    </div>
  )
}
