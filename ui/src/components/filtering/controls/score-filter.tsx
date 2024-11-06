import { Slider } from 'nova-ui-kit'
import { useEffect, useState } from 'react'
import { useFilters } from 'utils/useFilters'
import { useUserPreferences } from 'utils/userPreferences/userPreferencesContext'

const FILTER_FIELD = 'classification_threshold'

export const ScoreFilter = () => {
  const { filters, addFilter } = useFilters()
  const { userPreferences, setUserPreferences } = useUserPreferences()
  const [displayValue, setDisplayValue] = useState(
    userPreferences.scoreThreshold
  )

  const value = filters.find((filter) => filter.field === FILTER_FIELD)?.value

  useEffect(() => {
    if (value?.length) {
      setDisplayValue(Number(value))
    }
  }, [value])

  return (
    <div className="h-12 flex items-center">
      <Slider
        min={0}
        max={1}
        step={0.01}
        value={[displayValue]}
        onValueChange={([value]) => setDisplayValue(value)}
        onValueCommit={([value]) => {
          setDisplayValue(value)
          addFilter(FILTER_FIELD, `${value}`)
          setUserPreferences({ ...userPreferences, scoreThreshold: value })
        }}
      />
      <span className="w-12 text-right body-overline text-muted-foreground">
        {displayValue}
      </span>
    </div>
  )
}
