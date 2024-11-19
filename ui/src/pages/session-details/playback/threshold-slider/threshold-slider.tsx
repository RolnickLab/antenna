import { Slider } from 'nova-ui-kit'
import { useState } from 'react'
import { STRING, translate } from 'utils/language'
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
    <div className="w-full h-12 flex items-center gap-4 text-generic-white">
      <span className="body-overline-small font-bold">
        {translate(STRING.FIELD_LABEL_SCORE)}
      </span>
      <Slider
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
