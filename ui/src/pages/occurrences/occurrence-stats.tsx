import { ChevronsUpDown } from 'lucide-react'
import { useModelAgreement } from 'data-services/hooks/occurrences/stats/useModelAgreement'
import { Box, Button, Collapsible, InfoTooltip } from 'nova-ui-kit'
import { ReactNode } from 'react'

interface OccurrenceStatsProps {
  projectId?: string
  filters: { field: string; value?: string; error?: string }[]
}

const clampPct = (value: number) =>
  Math.round(Math.min(Math.max(value, 0), 1) * 100)

// "<1%" reads better than "0%" when the count is non-zero but rounds down.
const pctText = (value: number, count?: number) => {
  const pct = clampPct(value)
  return pct === 0 && count ? '<1%' : `${pct}%`
}

// Label + info tooltip. The tooltip carries the exact counts and the longer
// explanation so the row itself stays uncluttered. Text styles match the
// filter controls (body-overline-small).
const StatLabel = ({ label, tooltip }: { label: string; tooltip: string }) => (
  <div className="min-h-6 flex items-center gap-1">
    <span className="body-overline-small font-bold text-muted-foreground">
      {label}
    </span>
    <InfoTooltip text={tooltip} />
  </div>
)

// Simple progress bar: gray track + primary fill from the left. `fill` is the
// point estimate (0–1); `valueText` is the headline shown beside the bar (the
// CI range for agreement metrics, the raw percentage for verified). One shape
// for every non-signed metric — no separate CI whisker visualization.
const Bar = ({
  label,
  tooltip,
  fill,
  valueText,
}: {
  label: string
  tooltip: string
  fill: number
  valueText: ReactNode
}) => (
  <div className="space-y-2">
    <StatLabel label={label} tooltip={tooltip} />
    <div className="flex items-center gap-3">
      <div className="h-2 flex-1 rounded-full bg-border">
        <div
          className="h-2 rounded-full bg-primary transition-all"
          style={{ width: `${clampPct(fill)}%` }}
        />
      </div>
      <span className="body-base tabular-nums whitespace-nowrap">
        {valueText}
      </span>
    </div>
  </div>
)

// Agreement bar: a solid "confident floor" fills up to the lower 95% CI bound,
// then a diagonal hatch covers the CI range (ciLow–ciHigh) — the uncertain zone
// where the true value sits. The hatch is drawn over the gray track, not over
// the solid fill, so it stays visible regardless of where the point estimate
// lands (a near-100% point estimate previously hid blue-on-blue hatching).
// currentColor + text-primary avoids hardcoding the theme color. With no CI
// (e.g. coarser-rank), it falls back to a plain solid fill to the point value.
const AgreementBar = ({
  label,
  tooltip,
  value,
  ciLow,
  ciHigh,
  valueText,
}: {
  label: string
  tooltip: string
  value: number
  ciLow?: number | null
  ciHigh?: number | null
  valueText: ReactNode
}) => {
  const hasCi = ciLow != null && ciHigh != null
  const lowPct = hasCi ? clampPct(ciLow as number) : 0
  const highPct = hasCi ? clampPct(ciHigh as number) : 0

  return (
    <div className="space-y-2">
      <StatLabel label={label} tooltip={tooltip} />
      <div className="flex items-center gap-3">
        <div className="h-2 flex-1 rounded-full bg-border relative overflow-hidden">
          {hasCi ? (
            <>
              {/* Confident floor: solid up to the lower CI bound. */}
              <div
                className="absolute inset-y-0 left-0 bg-primary"
                style={{ width: `${lowPct}%` }}
              />
              {/* Uncertain zone: diagonal hatch across the CI range, over the
                  gray track so it stays visible at any point estimate. */}
              <div
                className="absolute inset-y-0 text-primary"
                style={{
                  left: `${lowPct}%`,
                  width: `${Math.max(highPct - lowPct, 1)}%`,
                  backgroundImage:
                    'repeating-linear-gradient(45deg, currentColor 0, currentColor 2px, transparent 2px, transparent 4px)',
                }}
                aria-label="95% confidence interval"
              />
            </>
          ) : (
            <div
              className="absolute inset-y-0 left-0 bg-primary"
              style={{ width: `${clampPct(value)}%` }}
            />
          )}
        </div>
        <span className="body-base tabular-nums whitespace-nowrap">
          {valueText}
        </span>
      </div>
    </div>
  )
}

// Signed bar for Cohen's kappa in [-1, 1]. 0 sits at the visual midpoint;
// positive fills rightward, negative leftward. Null → "—" (kappa is undefined
// for empty or single-category sets).
const SignedBar = ({
  label,
  tooltip,
  value,
}: {
  label: string
  tooltip: string
  value: number | null
}) => {
  const v = value === null ? null : Math.min(Math.max(value, -1), 1)
  const widthPct = v === null ? 0 : Math.abs(v) * 50
  const leftPct = v === null ? 50 : v >= 0 ? 50 : 50 - widthPct

  return (
    <div className="space-y-2">
      <StatLabel label={label} tooltip={tooltip} />
      <div className="flex items-center gap-3">
        <div className="h-2 flex-1 rounded-full bg-border relative">
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

// Headline beside an agreement bar: the 95% CI range when present, otherwise
// the point estimate. Exact counts live in the tooltip.
const ciRangeText = (
  pct: number,
  ciLow?: number | null,
  ciHigh?: number | null
) => {
  if (
    ciLow !== null &&
    ciLow !== undefined &&
    ciHigh !== null &&
    ciHigh !== undefined
  ) {
    return `${clampPct(ciLow)}–${clampPct(ciHigh)}%`
  }
  return `${clampPct(pct)}%`
}

// CI suffix for tooltip text, e.g. " 95% CI 83–94%." Empty when absent.
const ciTooltip = (ciLow?: number | null, ciHigh?: number | null) => {
  if (
    ciLow !== null &&
    ciLow !== undefined &&
    ciHigh !== null &&
    ciHigh !== undefined
  ) {
    return ` 95% CI ${clampPct(ciLow)}–${clampPct(ciHigh)}%.`
  }
  return ''
}

const StatsShell = ({ children }: { children: ReactNode }) => (
  <Box className="w-full h-min shrink-0 p-2 rounded-lg md:w-72 md:p-4 md:rounded-xl no-print">
    <span className="body-overline font-bold">Stats</span>
    <div className="mt-4 space-y-6">{children}</div>
  </Box>
)

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

  if (isLoading || !data) {
    return (
      <StatsShell>
        <div className="h-12 animate-pulse rounded-md bg-muted" />
        <div className="h-12 animate-pulse rounded-md bg-muted" />
      </StatsShell>
    )
  }

  const denom = data.verified_with_prediction_count.toLocaleString()
  const hasCoarser =
    data.agreement_coarsest_rank != null &&
    data.agreed_coarser_rank_pct !== null

  // Dynamic tooltip copy carrying the exact counts.
  const verifiedTooltip =
    `${data.verified_count.toLocaleString()} of ${data.total_occurrences.toLocaleString()} occurrences in the current filter are human-verified.` +
    (data.no_prediction_count > 0
      ? ` ${denom} of those have a model prediction to compare against.`
      : '')
  const exactTooltip =
    `The model's top prediction exactly matched the confirmed taxon for ` +
    `${data.agreed_exact_count.toLocaleString()} of ${denom} verified occurrences with a prediction ` +
    `(${clampPct(data.agreed_exact_pct)}%).` +
    ciTooltip(data.agreed_exact_ci_low, data.agreed_exact_ci_high)
  const anyRankTooltip =
    `The model's prediction matched the confirmed taxon at any rank (e.g. the right genus, ` +
    `even if the species differs) for ${data.agreed_any_rank_count.toLocaleString()} of ${denom} ` +
    `(${clampPct(data.agreed_any_rank_pct)}%).` +
    ciTooltip(data.agreed_any_rank_ci_low, data.agreed_any_rank_ci_high)

  return (
    <StatsShell>
      <Bar
        label="Verified occurrences"
        tooltip={verifiedTooltip}
        fill={data.verified_pct}
        valueText={pctText(data.verified_pct, data.verified_count)}
      />

      <AgreementBar
        label="Agreement (exact taxon)"
        tooltip={exactTooltip}
        value={data.agreed_exact_pct}
        ciLow={data.agreed_exact_ci_low}
        ciHigh={data.agreed_exact_ci_high}
        valueText={ciRangeText(
          data.agreed_exact_pct,
          data.agreed_exact_ci_low,
          data.agreed_exact_ci_high
        )}
      />

      <Collapsible.Root className="space-y-6" defaultOpen={false}>
        <Collapsible.Trigger asChild>
          <Button
            className="w-full justify-between px-0 text-muted-foreground"
            size="small"
            variant="ghost"
          >
            <span className="body-overline-small font-bold">More</span>
            <ChevronsUpDown className="h-4 w-4" />
          </Button>
        </Collapsible.Trigger>
        <Collapsible.Content className="space-y-6">
          <AgreementBar
            label="Agreement (any rank)"
            tooltip={anyRankTooltip}
            value={data.agreed_any_rank_pct}
            ciLow={data.agreed_any_rank_ci_low}
            ciHigh={data.agreed_any_rank_ci_high}
            valueText={ciRangeText(
              data.agreed_any_rank_pct,
              data.agreed_any_rank_ci_low,
              data.agreed_any_rank_ci_high
            )}
          />
          {hasCoarser ? (
            <Bar
              label={`Agreement (≥ ${data.agreement_coarsest_rank})`}
              tooltip={
                `The model agreed with the confirmed taxon at ${data.agreement_coarsest_rank} ` +
                `or coarser for ${(
                  data.agreed_coarser_rank_count as number
                ).toLocaleString()} of ${denom} ` +
                `(${clampPct(data.agreed_coarser_rank_pct as number)}%).`
              }
              fill={data.agreed_coarser_rank_pct as number}
              valueText={`${clampPct(data.agreed_coarser_rank_pct as number)}%`}
            />
          ) : null}
          <SignedBar
            label="Cohen's κ (beyond chance)"
            tooltip="Agreement beyond what random chance would produce, on exact-taxon matches. 0 means chance level, 1 means perfect agreement."
            value={data.cohens_kappa}
          />
        </Collapsible.Content>
      </Collapsible.Root>
    </StatsShell>
  )
}
