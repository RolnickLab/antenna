import {
  ModelAgreementResponse,
  useModelAgreement,
} from 'data-services/hooks/occurrences/stats/useModelAgreement'
import { ChevronsUpDown } from 'lucide-react'
import { Box, Button, Collapsible, InfoTooltip } from 'nova-ui-kit'
import { useState } from 'react'
import { STRING, translate } from 'utils/language'

interface OccurrenceStatsProps {
  projectId?: string
  filters: { field: string; value?: string; error?: string }[]
}

const clampPct = (value: number) =>
  Math.round(Math.min(Math.max(value, 0), 1) * 100)

// "<1%" reads better than "0%" when the count is non-zero but rounds down.
const pctText = (value: number, count: number) => {
  const pct = clampPct(value)
  return pct === 0 && count ? '<1%' : `${pct}%`
}

const ciRangeText = (
  pct: number,
  ciLow?: number | null,
  ciHigh?: number | null
) =>
  ciLow != null && ciHigh != null
    ? `${clampPct(ciLow)}–${clampPct(ciHigh)}%`
    : `${clampPct(pct)}%`

const StatLabel = ({ label, tooltip }: { label: string; tooltip: string }) => (
  <div className="min-h-6 flex items-center gap-1">
    <span className="body-overline-small font-bold text-muted-foreground">
      {label}
    </span>
    <InfoTooltip text={tooltip} />
  </div>
)

const Bar = ({
  label,
  tooltip,
  fill,
  valueText,
}: {
  label: string
  tooltip: string
  fill: number
  valueText: string
}) => (
  <div className="space-y-2">
    <StatLabel label={label} tooltip={tooltip} />
    <div className="flex items-center gap-3">
      <div
        aria-label={label}
        aria-valuemax={100}
        aria-valuemin={0}
        aria-valuenow={clampPct(fill)}
        aria-valuetext={valueText}
        className="h-2 flex-1 rounded-full bg-border"
        role="progressbar"
      >
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
  valueText: string
}) => {
  const hasCi = ciLow != null && ciHigh != null
  const lowPct = ciLow != null ? clampPct(ciLow) : 0
  const highPct = ciHigh != null ? clampPct(ciHigh) : 0

  return (
    <div className="space-y-2">
      <StatLabel label={label} tooltip={tooltip} />
      <div className="flex items-center gap-3">
        <div
          aria-label={label}
          aria-valuemax={100}
          aria-valuemin={0}
          aria-valuenow={clampPct(value)}
          aria-valuetext={valueText}
          className="h-2 flex-1 rounded-full bg-border relative overflow-hidden"
          role="progressbar"
        >
          {hasCi ? (
            <>
              <div
                className="absolute inset-y-0 left-0 bg-primary"
                style={{ width: `${lowPct}%` }}
              />
              {/* The hatch marking the confidence interval is drawn over the
                  gray track, not the solid fill, so it stays visible when the
                  estimate sits near 100%. See #1308. */}
              <div
                className="absolute inset-y-0 text-primary"
                style={{
                  left: `${lowPct}%`,
                  width: `${Math.max(highPct - lowPct, 1)}%`,
                  backgroundImage:
                    'repeating-linear-gradient(45deg, currentColor 0, currentColor 2px, transparent 2px, transparent 4px)',
                }}
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

const SignedBar = ({
  label,
  tooltip,
  value,
}: {
  label: string
  tooltip: string
  value: number | null
}) => {
  const clamped = value === null ? null : Math.min(Math.max(value, -1), 1)
  const widthPct = clamped === null ? 0 : Math.abs(clamped) * 50
  const leftPct =
    clamped === null ? 50 : clamped >= 0 ? 50 : 50 - Math.abs(clamped) * 50
  const valueText =
    clamped === null
      ? translate(STRING.VALUE_NOT_AVAILABLE)
      : clamped.toFixed(2)

  return (
    <div className="space-y-2">
      <StatLabel label={label} tooltip={tooltip} />
      <div className="flex items-center gap-3">
        <div
          aria-label={label}
          aria-valuemax={1}
          aria-valuemin={-1}
          aria-valuenow={clamped ?? undefined}
          aria-valuetext={valueText}
          className="h-2 flex-1 rounded-full bg-border relative"
          role="progressbar"
        >
          <div className="absolute h-2 w-px bg-foreground/40 left-1/2" />
          {clamped !== null ? (
            <div
              className="absolute h-2 rounded-full bg-primary transition-all"
              style={{ left: `${leftPct}%`, width: `${widthPct}%` }}
            />
          ) : null}
        </div>
        <span className="body-base tabular-nums">{valueText}</span>
      </div>
    </div>
  )
}

// Live verified / agreement stats for the occurrence list. Threads the same
// filter array the list view sends so the numbers always match the result set.
// Collapsed by default, and the query only runs while it is open.
export const OccurrenceStats = ({
  projectId,
  filters,
}: OccurrenceStatsProps) => {
  const [open, setOpen] = useState(false)

  const activeFilters = filters.reduce<Record<string, string>>(
    (acc, { field, value, error }) => {
      if (value?.length && !error) {
        acc[field] = value
      }
      return acc
    },
    {}
  )

  const { data, error } = useModelAgreement(projectId, activeFilters, open)

  return (
    <Box className="w-full h-min shrink-0 p-2 rounded-lg md:w-72 md:p-4 md:rounded-xl no-print">
      <Collapsible.Root
        className="space-y-4"
        onOpenChange={setOpen}
        open={open}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1">
            <span className="body-overline font-bold">
              {translate(STRING.STATS)}
            </span>
            <InfoTooltip text={translate(STRING.TOOLTIP_STATS)} />
          </div>
          <Collapsible.Trigger asChild>
            <Button
              aria-label={translate(open ? STRING.COLLAPSE : STRING.EXPAND)}
              size="icon"
              variant="ghost"
            >
              <ChevronsUpDown className="h-4 w-4" />
            </Button>
          </Collapsible.Trigger>
        </div>
        <Collapsible.Content className="space-y-6">
          <StatsContent data={data} error={error} />
        </Collapsible.Content>
      </Collapsible.Root>
    </Box>
  )
}

const StatsContent = ({
  data,
  error,
}: {
  data?: ModelAgreementResponse
  error?: unknown
}) => {
  if (error) {
    return (
      <span className="body-small text-muted-foreground">
        {translate(STRING.UNKNOWN_ERROR)}
      </span>
    )
  }

  if (!data) {
    return (
      <>
        <div className="h-12 animate-pulse rounded-md bg-muted" />
        <div className="h-12 animate-pulse rounded-md bg-muted" />
      </>
    )
  }

  const comparable = data.comparable_count
  const hasCoarser =
    data.agreement_coarsest_rank != null && data.agreed_coarser_rank_pct != null

  return (
    <>
      <Bar
        fill={data.verified_pct}
        label={translate(STRING.VERIFIED_OCCURRENCES)}
        tooltip={translate(STRING.TOOLTIP_STATS_VERIFIED, {
          comparable,
          total: data.total_occurrences,
          verified: data.verified_count,
        })}
        valueText={pctText(data.verified_pct, data.verified_count)}
      />

      {comparable === 0 ? (
        <span className="body-small text-muted-foreground">
          {translate(STRING.MESSAGE_STATS_NO_COMPARABLE)}
        </span>
      ) : (
        <>
          <AgreementBar
            ciHigh={data.agreed_exact_ci_high}
            ciLow={data.agreed_exact_ci_low}
            label={translate(STRING.AGREEMENT_EXACT)}
            tooltip={translate(STRING.TOOLTIP_STATS_AGREEMENT_EXACT, {
              comparable,
              count: data.agreed_exact_count,
              pct: clampPct(data.agreed_exact_pct),
            })}
            value={data.agreed_exact_pct}
            valueText={ciRangeText(
              data.agreed_exact_pct,
              data.agreed_exact_ci_low,
              data.agreed_exact_ci_high
            )}
          />

          <Collapsible.Root className="space-y-6">
            <Collapsible.Trigger asChild>
              <Button
                className="w-full justify-between px-0 text-muted-foreground"
                size="small"
                variant="ghost"
              >
                <span className="body-overline-small font-bold">
                  {translate(STRING.MORE)}
                </span>
                <ChevronsUpDown className="h-4 w-4" />
              </Button>
            </Collapsible.Trigger>
            <Collapsible.Content className="space-y-6">
              <AgreementBar
                ciHigh={data.agreed_any_rank_ci_high}
                ciLow={data.agreed_any_rank_ci_low}
                label={translate(STRING.AGREEMENT_ANY_RANK)}
                tooltip={translate(STRING.TOOLTIP_STATS_AGREEMENT_ANY_RANK, {
                  comparable,
                  count: data.agreed_any_rank_count,
                  pct: clampPct(data.agreed_any_rank_pct),
                })}
                value={data.agreed_any_rank_pct}
                valueText={ciRangeText(
                  data.agreed_any_rank_pct,
                  data.agreed_any_rank_ci_low,
                  data.agreed_any_rank_ci_high
                )}
              />
              {hasCoarser && data.agreed_coarser_rank_pct != null ? (
                <Bar
                  fill={data.agreed_coarser_rank_pct}
                  label={translate(STRING.AGREEMENT_COARSER_RANK, {
                    rank: data.agreement_coarsest_rank as string,
                  })}
                  tooltip={translate(
                    STRING.TOOLTIP_STATS_AGREEMENT_COARSER_RANK,
                    {
                      comparable,
                      count: data.agreed_coarser_rank_count ?? 0,
                      pct: clampPct(data.agreed_coarser_rank_pct),
                      rank: data.agreement_coarsest_rank as string,
                    }
                  )}
                  valueText={`${clampPct(data.agreed_coarser_rank_pct)}%`}
                />
              ) : null}
              <SignedBar
                label={translate(STRING.AGREEMENT_KAPPA)}
                tooltip={translate(STRING.TOOLTIP_STATS_KAPPA)}
                value={data.cohens_kappa}
              />
            </Collapsible.Content>
          </Collapsible.Root>
        </>
      )}
    </>
  )
}
