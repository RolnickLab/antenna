import { Tooltip } from 'design-system/components/tooltip/tooltip'
import { Fragment } from 'react'
import { Link } from 'react-router-dom'
import { Icon, IconTheme, IconType } from '../../icon/icon'
import styles from './taxon-ranks.module.scss'

interface TaxonRanksProps {
  ranks: {
    id: string
    name: string
    rank: string
    to?: string
  }[]
}

export const TaxonRanks = ({ ranks }: TaxonRanksProps) => (
  <div className={styles.ranks}>
    {ranks.map((r, index) => (
      <Fragment key={r.id}>
        {r.to ? (
          <Tooltip content={r.rank}>
            <span className={styles.rank}>
              <Link to={r.to}>{r.name}</Link>
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
