import { useModelAgreement } from 'data-services/hooks/occurrences/stats/useModelAgreement'
import { Box } from 'nova-ui-kit'

interface OccurrenceStatsProps {
  projectId?: string
  filters: { field: string; value?: string; error?: string }[]
}

const StatBar = ({
  label,
  value,
  count,
}: {
  label: string
  value: number
  // Optional raw count shown alongside the percentage, e.g. "0% (23)". Useful
  // when the percentage rounds to 0 but the underlying count is non-zero.
  count?: number
}) => {
  const pct = Math.round(Math.min(Math.max(value, 0), 1) * 100)

  return (
    <div className="space-y-2">
      <span className="body-overline font-bold text-muted-foreground">
        {label}
      </span>
      <div className="flex items-center gap-3">
        <div className="h-2 flex-1 rounded-full bg-muted">
          <div
            className="h-2 rounded-full bg-primary transition-all"
            style={{ width: `${pct}%` }}
          />
        </div>
        <span className="body-base tabular-nums">
          {pct}%
          {count !== undefined ? (
            <span className="text-muted-foreground">
              {' '}
              ({count.toLocaleString()})
            </span>
          ) : null}
        </span>
      </div>
    </div>
  )
}

// Live verified / agreement stats for the occurrence list. Threads the same
// filter array the list view sends so the numbers always match the result set.
export const OccurrenceStats = ({
  projectId,
  filters,
}: OccurrenceStatsProps) => {
  const activeFilters = filters.reduce<Record<string, string>>(
    (acc, { field, value, error }) => {
      if (value?.length && !error) {
        acc[field] = value
      }
      return acc
    },
    {}
  )

  const { data, isLoading, error } = useModelAgreement(projectId, activeFilters)

  if (error || (!isLoading && !data)) {
    return null
  }

  return (
    <Box className="w-full h-min shrink-0 p-2 rounded-lg md:w-72 md:p-4 md:rounded-xl no-print">
      <span className="body-overline font-bold">Stats</span>
      <div className="mt-4 space-y-6">
        {isLoading || !data ? (
          <>
            <div className="h-12 animate-pulse rounded-md bg-muted" />
            <div className="h-12 animate-pulse rounded-md bg-muted" />
          </>
        ) : (
          <>
            <StatBar
              label="Verified occurrences"
              value={data.verified_pct}
              count={data.verified_count}
            />
            <StatBar
              label="Human-model agreement rate"
              value={data.agreed_any_rank_pct}
            />
          </>
        )}
      </div>
    </Box>
  )
}
