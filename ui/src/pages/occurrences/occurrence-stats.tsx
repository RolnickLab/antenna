import { useModelAgreement } from 'data-services/hooks/occurrences/stats/useModelAgreement'
import { Box } from 'nova-ui-kit'

interface OccurrenceStatsProps {
  projectId?: string
  filters: { field: string; value?: string; error?: string }[]
}

const clampPct = (value: number) =>
  Math.round(Math.min(Math.max(value, 0), 1) * 100)

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
  const pct = clampPct(value)

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

// Combined point estimate + Wilson 95% CI in one bar so the uncertainty is
// adjacent to the number it qualifies (more visible than the previous
// separate-row RangeBar). Layout per row:
//
//   Label
//   [ ━━━━┃══════╋══════┃━━━━ ]   pct% (k of n)   low–high% CI
//          ^cap  ^point  ^cap
//
// The full track is 0–100%. The CI band is a translucent fill from low to
// high. Small vertical caps mark the CI bounds (error-bar whiskers). A solid
// vertical line marks the point estimate. When CI bounds are absent (e.g.
// `agreed_coarser_rank` has no CI in the BE response), just the bar + point
// render.
const AgreementBar = ({
  label,
  value,
  count,
  total,
  ciLow,
  ciHigh,
}: {
  label: string
  value: number
  count?: number
  total?: number
  ciLow?: number | null
  ciHigh?: number | null
}) => {
  const pct = clampPct(value)
  const hasCi =
    ciLow !== null &&
    ciLow !== undefined &&
    ciHigh !== null &&
    ciHigh !== undefined
  const lowPct = hasCi ? clampPct(ciLow as number) : 0
  const highPct = hasCi ? clampPct(ciHigh as number) : 0

  return (
    <div className="space-y-2">
      <span className="body-overline font-bold text-muted-foreground">
        {label}
      </span>
      <div className="space-y-1">
        <div className="flex items-center gap-3">
          <div className="h-3 flex-1 rounded-full bg-muted relative overflow-hidden">
            {hasCi ? (
              <>
                <div
                  className="absolute top-0 h-3 bg-primary/40"
                  style={{
                    left: `${lowPct}%`,
                    width: `${Math.max(highPct - lowPct, 0.5)}%`,
                  }}
                  aria-label="95% confidence interval"
                />
                <div
                  className="absolute top-0 h-3 w-[2px] bg-primary"
                  style={{ left: `calc(${lowPct}% - 1px)` }}
                />
                <div
                  className="absolute top-0 h-3 w-[2px] bg-primary"
                  style={{ left: `calc(${highPct}% - 1px)` }}
                />
              </>
            ) : null}
            <div
              className="absolute top-[-2px] h-[16px] w-[3px] rounded-sm bg-foreground transition-all"
              style={{ left: `calc(${pct}% - 1.5px)` }}
              aria-label="point estimate"
            />
          </div>
          <span className="body-base tabular-nums whitespace-nowrap">
            {pct}%
            {count !== undefined ? (
              <span className="text-muted-foreground">
                {total !== undefined
                  ? ` (${count.toLocaleString()} of ${total.toLocaleString()})`
                  : ` (${count.toLocaleString()})`}
              </span>
            ) : null}
          </span>
        </div>
        {hasCi ? (
          <div className="body-small tabular-nums text-muted-foreground">
            95% CI {lowPct}–{highPct}%
          </div>
        ) : null}
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

  const hasCoarser =
    data?.agreement_coarsest_rank != null &&
    data?.agreed_coarser_rank_pct !== null

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
            <AgreementBar
              label="Agreement (exact taxon)"
              value={data.agreed_exact_pct}
              count={data.agreed_exact_count}
              total={data.verified_with_prediction_count}
              ciLow={data.agreed_exact_ci_low}
              ciHigh={data.agreed_exact_ci_high}
            />
            <AgreementBar
              label="Agreement (any rank)"
              value={data.agreed_any_rank_pct}
              count={data.agreed_any_rank_count}
              total={data.verified_with_prediction_count}
              ciLow={data.agreed_any_rank_ci_low}
              ciHigh={data.agreed_any_rank_ci_high}
            />
            {hasCoarser ? (
              <AgreementBar
                label={`Agreement (≥ ${data.agreement_coarsest_rank})`}
                value={data.agreed_coarser_rank_pct as number}
                count={data.agreed_coarser_rank_count as number}
                total={data.verified_with_prediction_count}
              />
            ) : null}
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
