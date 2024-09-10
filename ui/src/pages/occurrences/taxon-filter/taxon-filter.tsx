import { Taxon } from 'data-services/models/taxa'
import { TaxonSearch } from 'pages/occurrence-details/taxon-search/taxon-search'
import { useEffect, useRef, useState } from 'react'
import { useFilters } from 'utils/useFilters'
import styles from './taxon-filter.module.scss'

const FILTER_FIELD = 'determination'

export const TaxonFilter = () => {
  const containerRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const [taxon, setTaxon] = useState<Taxon>()
  const { filters, addFilter, clearFilter } = useFilters()

  useEffect(() => {
    // Clear taxon if determination filter is cleared
    const currentFilter = filters.find(
      (filter) => filter.field === FILTER_FIELD
    )

    if (currentFilter?.value === undefined) {
      setTaxon(undefined)
    }
  }, [filters])

  return (
    <div ref={containerRef} className={styles.container}>
      <TaxonSearch
        autoFocus={false}
        containerRef={containerRef}
        inputRef={inputRef}
        taxon={taxon}
        onTaxonChange={(taxon) => {
          setTaxon(taxon)
          if (taxon) {
            addFilter(FILTER_FIELD, taxon.id)
          } else {
            clearFilter(FILTER_FIELD)
          }
        }}
      />
    </div>
  )
}
