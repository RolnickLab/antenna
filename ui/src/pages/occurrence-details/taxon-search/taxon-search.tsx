import { Taxon } from 'data-services/models/taxa'
import { ComboBoxTree } from 'design-system/components/combo-box/combo-box-tree/combo-box-tree'
import { RefObject, useMemo, useState } from 'react'
import { STRING, translate } from 'utils/language'
import { useDebounce } from 'utils/useDebounce'
import { useTaxonSearch } from './useTaxonSearch'

export const TaxonSearch = ({
  containerRef,
  inputRef,
  taxon,
  onTaxonChange,
}: {
  containerRef: RefObject<HTMLDivElement>
  inputRef: RefObject<HTMLInputElement>
  taxon?: Taxon
  onTaxonChange: (taxon?: Taxon) => void
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
    <ComboBoxTree
      containerRef={containerRef}
      emptyLabel={translate(STRING.MESSAGE_NO_RESULTS)}
      inputRef={inputRef}
      loading={isLoading}
      nodes={nodes}
      searchString={searchString}
      selectedLabel={taxon?.name}
      selectedNodeId={taxon?.id}
      onItemSelect={(id) => {
        const taxon = id ? data?.find((i) => i.id === id) : undefined
        onTaxonChange(taxon)
      }}
      setSearchString={setSearchString}
    />
  )
}
