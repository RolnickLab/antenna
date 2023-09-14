import { ComboBox } from 'design-system/components/combo-box/combo-box'
import { useMemo, useState } from 'react'
import { STRING, translate } from 'utils/language'
import { useDebounce } from 'utils/useDebounce'
import { useTaxonSearch } from './useTaxonSearch'

export const TaxonSearch = () => {
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
    }))
  }, [data])

  return (
    <ComboBox
      emptyLabel={translate(STRING.MESSAGE_NO_RESULTS)}
      items={items}
      label="Suggest ID"
      searchString={searchString}
      shouldFilter={false}
      onItemSelect={(id) => {
        const item = data?.find((i) => i.id === id)
        if (item) {
          setSearchString(item.name)
          // TODO: Call on change
        }
      }}
      setSearchString={setSearchString}
    />
  )
}
