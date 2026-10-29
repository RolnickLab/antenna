import { Fragment, ReactNode } from 'react'

export interface HistoryStat {
  label: string
  value: ReactNode
}

// Labels get at most 40% of the width and wrap first, so values keep the room they need.
export const HistoryStats = ({ stats }: { stats: HistoryStat[] }) =>
  stats.length ? (
    <div className="grid grid-cols-[fit-content(40%)_minmax(0,1fr)] gap-x-6 gap-y-2 px-4 py-4 border-border border-t body-small">
      {stats.map(({ label, value }) => (
        <Fragment key={label}>
          <span className="text-muted-foreground">{label}</span>
          <span className="min-w-0 break-words text-foreground tabular-nums">
            {value}
          </span>
        </Fragment>
      ))}
    </div>
  ) : null

export const HistoryTime = ({ label }: { label: string }) => (
  <span className="block p-2 text-right text-muted-foreground body-overline-small normal-case">
    {label}
  </span>
)
