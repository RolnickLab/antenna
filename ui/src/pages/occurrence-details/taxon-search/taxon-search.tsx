import { Taxon } from 'data-services/models/taxa'
import { ComboBoxFlat } from 'design-system/components/combo-box/combo-box-flat'
import { useMemo, useState } from 'react'
import { STRING, translate } from 'utils/language'
import { useDebounce } from 'utils/useDebounce'
import { useTaxonSearch } from './useTaxonSearch'

export const TaxonSearch = ({
  taxon,
  onTaxonChange,
}: {
  taxon?: Taxon
  onTaxonChange: (taxon: Taxon) => void
}) => {
  const [searchString, setSearchString] = useState('')
  const debouncedSearchString = useDebounce(searchString, 200)
  const { data } = useTaxonSearch(debouncedSearchString)

  const items = useMemo(() => {
    if (!data?.length) {
      return []
    }
    return data.map((result) => ({
      id: result.id,
      label: result.name,
      details: result.rank,
    }))
  }, [data])

  return (
    <ComboBoxFlat
      emptyLabel={translate(STRING.MESSAGE_NO_RESULTS)}
      items={items}
      searchString={searchString}
      selectedItemId={taxon?.id}
      onItemSelect={(id) => {
        const taxon = data?.find((i) => i.id === id)
        if (taxon) {
          onTaxonChange(taxon)
        }
      }}
      setSearchString={setSearchString}
    />
  )
}
