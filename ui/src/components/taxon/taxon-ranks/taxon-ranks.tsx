import classNames from 'classnames'
import { Tooltip } from 'design-system/components/tooltip/tooltip'
import { Fragment } from 'react'
import { Link } from 'react-router-dom'
import styles from './taxon-ranks.module.scss'

interface TaxonRanksProps {
  compact?: boolean
  ranks: {
    id: string
    name: string
    rank: string
  }[]
  getLink?: (taxonId: string) => string
}

export const TaxonRanks = ({
  compact,
  ranks: _ranks,
  getLink,
}: TaxonRanksProps) => {
  const compactMode = compact && _ranks.length > 3
  const mainRank = compactMode ? _ranks[0] : undefined
  const ranks = compactMode ? _ranks.slice(-2) : _ranks

  return (
    <div
      className={classNames(styles.ranks, { [styles.compact]: compactMode })}
    >
      {mainRank && (
        <>
          <TaxonRank rank={mainRank} to={getLink?.(mainRank.id)} />
          <span className={classNames(styles.rank, styles.divider)}>|</span>
        </>
      )}
      {ranks.map((r, index) => (
        <Fragment key={r.id}>
          <TaxonRank rank={r} to={getLink?.(r.id)} />
          {index < ranks.length - 1 ? (
            <span className={classNames(styles.rank, styles.divider)}>›</span>
          ) : null}
        </Fragment>
      ))}
    </div>
  )
}

const TaxonRank = ({
  rank,
  to,
}: {
  rank: {
    name: string
    rank: string
  }
  to?: string
}) => (
  <>
    {to ? (
      <Tooltip content={rank.rank}>
        <span className={styles.rank}>
          <Link to={to}>{rank.name}</Link>
        </span>
      </Tooltip>
    ) : (
      <span className={styles.rank}>{rank.name}</span>
    )}
  </>
)
