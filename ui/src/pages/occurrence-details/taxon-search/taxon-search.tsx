import { Taxon } from 'data-services/models/taxa'
import { ComboBoxFlat } from 'design-system/components/combo-box/combo-box-flat'
import { RefObject, useMemo, useState } from 'react'
import { STRING, translate } from 'utils/language'
import { useDebounce } from 'utils/useDebounce'
import { useTaxonSearch } from './useTaxonSearch'

export const TaxonSearch = ({
  inputRef,
  taxon,
  onTaxonChange,
}: {
  inputRef: RefObject<HTMLInputElement>
  taxon?: Taxon
  onTaxonChange: (taxon: Taxon) => void
}) => {
  const [searchString, setSearchString] = useState('')
  const debouncedSearchString = useDebounce(searchString, 200)
  const { data, isLoading } = useTaxonSearch(debouncedSearchString)

  const nodes = useMemo(() => {
    if (!data?.length) {
      return []
    }

    return data.map((taxon) => ({
      id: taxon.id,
      label: taxon.name,
      details: taxon.rank,
      parentId: taxon.parentId,
    }))
  }, [data])

  return (
    <ComboBoxFlat
      emptyLabel={translate(STRING.MESSAGE_NO_RESULTS)}
      inputRef={inputRef}
      loading={isLoading}
      nodes={nodes}
      searchString={searchString}
      selectedNodeId={taxon?.id}
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
