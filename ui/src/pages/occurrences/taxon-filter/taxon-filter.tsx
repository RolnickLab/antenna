import { Taxon } from 'data-services/models/taxa'
import { TaxonSearch } from 'pages/occurrence-details/taxon-search/taxon-search'
import { useRef, useState } from 'react'
import { useFilters } from 'utils/useFilters'
import styles from './taxon-filter.module.scss'

export const TaxonFilter = () => {
  const containerRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const [taxon, setTaxon] = useState<Taxon>()
  const { addFilter, clearFilter } = useFilters()

  return (
    <div ref={containerRef} className={styles.container}>
      <TaxonSearch
        containerRef={containerRef}
        inputRef={inputRef}
        taxon={taxon}
        onTaxonChange={(taxon) => {
          setTaxon(taxon)
          if (taxon) {
            addFilter('determination', taxon.id)
          } else {
            clearFilter('determination')
          }
        }}
      />
    </div>
  )
}
