import classNames from 'classnames'
import { Taxon } from 'data-services/models/taxa'
import { TaxonRanks } from '../taxon-ranks/taxon-ranks'
import styles from './taxon-info.module.scss'

export enum TaxonInfoSize {
  Medium = 'medium',
  Large = 'large',
}

interface TaxonInfoProps {
  overridden?: boolean
  size?: TaxonInfoSize
  taxon: Taxon
  to?: string
}

export const TaxonInfo = ({
  overridden,
  size = TaxonInfoSize.Medium,
  taxon,
}: TaxonInfoProps) => (
  <div>
    <span
      className={classNames(styles.name, {
        [styles.overridden]: overridden,
        [styles.large]: size === TaxonInfoSize.Large,
      })}
    >
      {taxon.name}
    </span>
    {taxon.ranks ? <TaxonRanks ranks={taxon.ranks} /> : null}
  </div>
)
