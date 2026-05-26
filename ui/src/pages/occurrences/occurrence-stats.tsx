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

// Horizontal range bar for a Wilson confidence interval. Draws a filled
// segment between `low` and `high` over a 0–100% track, so a wide CI reads as
// a wide bar (= shaky number) and a tight CI as a narrow one. Null bounds →
// "—".
const RangeBar = ({
  label,
  low,
  high,
}: {
  label: string
  low: number | null
  high: number | null
}) => {
  const hasData = low !== null && high !== null
  const lowPct = hasData ? Math.round(Math.min(Math.max(low, 0), 1) * 100) : 0
  const highPct = hasData ? Math.round(Math.min(Math.max(high, 0), 1) * 100) : 0

  return (
    <div className="space-y-2">
      <span className="body-overline font-bold text-muted-foreground">
        {label}
      </span>
      <div className="flex items-center gap-3">
        <div className="h-2 flex-1 rounded-full bg-muted relative">
          {hasData ? (
            <div
              className="absolute h-2 rounded-full bg-primary transition-all"
              style={{
                left: `${lowPct}%`,
                width: `${Math.max(highPct - lowPct, 1)}%`,
              }}
            />
          ) : null}
        </div>
        <span className="body-base tabular-nums">
          {hasData ? `${lowPct}–${highPct}%` : '—'}
        </span>
      </div>
    </div>
  )
}

// Signed bar for a value in [-1, 1] (Cohen's kappa). 0 sits at the visual
// midpoint; positive values fill rightward, negative fill leftward. Null →
// "—" (kappa is undefined for empty or single-category sets).
const SignedBar = ({
  label,
  value,
}: {
  label: string
  value: number | null
}) => {
  const v = value === null ? null : Math.min(Math.max(value, -1), 1)
  const widthPct = v === null ? 0 : Math.abs(v) * 50
  const leftPct = v === null ? 50 : v >= 0 ? 50 : 50 - widthPct

  return (
    <div className="space-y-2">
      <span className="body-overline font-bold text-muted-foreground">
        {label}
      </span>
      <div className="flex items-center gap-3">
        <div className="h-2 flex-1 rounded-full bg-muted relative">
          {/* zero marker */}
          <div className="absolute h-2 w-px bg-foreground/40 left-1/2" />
          {v !== null ? (
            <div
              className="absolute h-2 rounded-full bg-primary transition-all"
              style={{ left: `${leftPct}%`, width: `${widthPct}%` }}
            />
          ) : null}
        </div>
        <span className="body-base tabular-nums">
          {v === null ? '—' : v.toFixed(2)}
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
            <RangeBar
              label="Agreement 95% CI (Wilson)"
              low={data.agreed_any_rank_ci_low}
              high={data.agreed_any_rank_ci_high}
            />
            <SignedBar
              label="Cohen's κ (beyond chance)"
              value={data.cohens_kappa}
            />
          </>
        )}
      </div>
    </Box>
  )
}
