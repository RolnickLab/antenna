import classNames from 'classnames'
import { Taxon } from 'data-services/models/taxa'
import { Tooltip } from 'design-system/components/tooltip/tooltip'
import { Link } from 'react-router-dom'
import { TaxonRanks } from '../taxon-ranks/taxon-ranks'
import styles from './taxon-info.module.scss'

export enum TaxonInfoSize {
  Medium = 'medium',
  Large = 'large',
}

interface TaxonInfoProps {
  compact?: boolean
  overridden?: boolean
  size?: TaxonInfoSize
  taxon: Taxon
  getLink?: (taxonId: string) => string
}

export const TaxonInfo = ({
  compact,
  overridden,
  size,
  taxon,
  getLink,
}: TaxonInfoProps) => {
  const nameClasses = classNames(styles.name, {
    [styles.overridden]: overridden,
    [styles.large]: size === TaxonInfoSize.Large,
  })

  return (
    <div>
      {getLink ? (
        <Tooltip content={taxon.rank}>
          <span className={nameClasses}>
            <Link to={getLink(taxon.id)}>{taxon.name}</Link>
          </span>
        </Tooltip>
      ) : (
        <span className={nameClasses}>{taxon.name}</span>
      )}
      {taxon.ranks ? (
        <TaxonRanks compact={compact} ranks={taxon.ranks} getLink={getLink} />
      ) : null}
    </div>
  )
}
