import { Slider } from 'nova-ui-kit'
import { useEffect, useState } from 'react'
import { useUserPreferences } from 'utils/userPreferences/userPreferencesContext'
import { FilterProps } from './types'

export const ScoreFilter = ({ value, onAdd }: FilterProps) => {
  const { userPreferences, setUserPreferences } = useUserPreferences()
  const [displayValue, setDisplayValue] = useState(
    userPreferences.scoreThreshold
  )

  useEffect(() => {
    if (value?.length) {
      setDisplayValue(Number(value))
    }
  }, [value])

  return (
    <div className="w-full h-12 flex items-center">
      <Slider
        min={0}
        max={1}
        step={0.01}
        value={[displayValue]}
        onValueChange={([value]) => setDisplayValue(value)}
        onValueCommit={([value]) => {
          setDisplayValue(value)
          onAdd(`${value}`)
          setUserPreferences({ ...userPreferences, scoreThreshold: value })
        }}
      />
      <span className="w-12 text-right body-overline text-muted-foreground">
        {displayValue}
      </span>
    </div>
  )
}
