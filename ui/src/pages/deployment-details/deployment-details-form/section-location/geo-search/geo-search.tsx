import { ComboBoxSimple } from 'design-system/components/combo-box/combo-box-simple/combo-box-simple'
import { MarkerPosition } from 'design-system/map/types'
import { useMemo, useState } from 'react'
import { STRING, translate } from 'utils/language'
import { useDebounce } from 'utils/useDebounce'
import { useGeoSearch } from './useGeoSearch'

export const GeoSearch = ({
  onPositionChange,
}: {
  onPositionChange: (position: MarkerPosition) => void
}) => {
  const [searchString, setSearchString] = useState('')
  const debouncedSearchString = useDebounce(searchString, 200)
  const { data, isLoading } = useGeoSearch(debouncedSearchString)

  const items = useMemo(() => {
    if (!data?.length) {
      return []
    }
    return data.map((result) => ({
      id: result.osmId,
      label: result.displayName,
    }))
  }, [data])

  return (
    <ComboBoxSimple
      emptyLabel={translate(STRING.MESSAGE_NO_RESULTS)}
      items={items}
      label={translate(STRING.SEARCH_MAP)}
      loading={isLoading}
      searchString={searchString}
      onItemSelect={(id) => {
        const item = data?.find((i) => i.osmId === id)
        if (item) {
          setSearchString(item.displayName)
          onPositionChange(item.position)
        }
      }}
      setSearchString={setSearchString}
    />
  )
}
