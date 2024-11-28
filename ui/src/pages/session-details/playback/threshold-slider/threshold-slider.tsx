import { Slider } from 'nova-ui-kit'
import { useState } from 'react'
import { useUserPreferences } from 'utils/userPreferences/userPreferencesContext'

export const ThresholdSlider = () => {
  const [active, setActive] = useState(false)
  const { userPreferences, setUserPreferences } = useUserPreferences()
  const [displayThreshold, setDisplayThreshold] = useState(
    userPreferences.scoreThreshold
  )

  const onValueCommit = (value: number) => {
    setDisplayThreshold(value)
    setUserPreferences({
      ...userPreferences,
      scoreThreshold: value,
    })
  }

  return (
    <div className="w-full h-12 flex items-center text-generic-white">
      <Slider
        className="[&_.track]:bg-secondary [&_.thumb]:border-secondary"
        invertedColors
        defaultValue={[userPreferences.scoreThreshold]}
        min={0}
        max={1}
        step={0.01}
        value={[displayThreshold]}
        onValueChange={([value]) => setDisplayThreshold(value)}
        onValueCommit={([value]) => onValueCommit(value)}
        onPointerDown={() => setActive(true)}
        onPointerUp={() => setActive(false)}
        onPointerLeave={() => {
          if (active) {
            onValueCommit(displayThreshold)
          }
        }}
      />
      <span className="w-12 text-right body-overline">{displayThreshold}</span>
    </div>
  )
}
