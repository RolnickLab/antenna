import { Icon, IconTheme, IconType } from 'design-system/components/icon/icon'
import { Tooltip } from 'design-system/components/tooltip/tooltip'
import { Fragment } from 'react'
import { Link } from 'react-router-dom'
import styles from './taxon-ranks.module.scss'

interface TaxonRanksProps {
  ranks: {
    id: number
    name: string
    rank: string
  }[]
  getLink?: (taxonId: number) => string
}

export const TaxonRanks = ({ ranks, getLink }: TaxonRanksProps) => (
  <div className={styles.ranks}>
    {ranks.map((r, index) => (
      <Fragment key={r.id}>
        {getLink ? (
          <Tooltip content={r.rank}>
            <span className={styles.rank}>
              <Link to={getLink(r.id)}>{r.name}</Link>
            </span>
          </Tooltip>
        ) : (
          <span className={styles.rank}>{r.name}</span>
        )}
        {index < ranks.length - 1 ? (
          <Icon
            type={IconType.ToggleRight}
            theme={IconTheme.Neutral}
            size={8}
          />
        ) : null}
      </Fragment>
    ))}
  </div>
)
