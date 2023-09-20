import { Taxon } from 'data-services/models/taxa'
import { ComboBox } from 'design-system/components/combo-box/combo-box'
import { useMemo, useState } from 'react'
import { STRING, translate } from 'utils/language'
import { useDebounce } from 'utils/useDebounce'
import { useTaxonSearch } from './useTaxonSearch'

export const TaxonSearch = ({
  onChange,
}: {
  onChange: (taxon: Taxon) => void
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
    <ComboBox
      defaultOpen
      emptyLabel={translate(STRING.MESSAGE_NO_RESULTS)}
      items={items}
      label="Search"
      searchString={searchString}
      shouldFilter={false}
      onItemSelect={(id) => {
        const taxon = data?.find((i) => i.id === id)
        if (taxon) {
          onChange(taxon)
        }
      }}
      setSearchString={setSearchString}
    />
  )
}
