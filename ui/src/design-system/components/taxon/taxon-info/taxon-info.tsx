import classNames from 'classnames'
import { Taxon } from 'data-services/models/taxa'
import { TaxonRanks } from '../taxon-ranks/taxon-ranks'
import styles from './taxon-info.module.scss'

interface TaxonInfoProps {
  taxon?: Taxon
  overridden?: boolean
}

export const TaxonInfo = ({ overridden, taxon }: TaxonInfoProps) => (
  <div>
    <span
      className={classNames(styles.name, {
        [styles.overridden]: overridden,
      })}
    >
      {taxon?.name ?? 'Unknown Taxon'}
    </span>
    <TaxonRanks ranks={taxon?.ranks ?? []} />
  </div>
)
