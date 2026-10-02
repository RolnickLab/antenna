import { Fragment, ReactNode } from 'react'

export interface HistoryStat {
  label: string
  value: ReactNode
}

export const HistoryStats = ({ stats }: { stats: HistoryStat[] }) =>
  stats.length ? (
    <div className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-2 px-4 py-4 border-border border-t body-small">
      {stats.map(({ label, value }) => (
        <Fragment key={label}>
          <span className="text-muted-foreground">{label}</span>
          <span className="text-foreground tabular-nums">{value}</span>
        </Fragment>
      ))}
    </div>
  ) : null

export const HistoryTime = ({ label }: { label: string }) => (
  <span className="block p-2 text-right text-muted-foreground body-overline-small normal-case">
    {label}
  </span>
)

export const HistoryTypeBadge = ({ label }: { label: string }) => (
  <span className="px-2 py-0.5 rounded-full border border-border body-small text-muted-foreground">
    {label}
  </span>
)
