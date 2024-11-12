import { ScoreSlider } from 'design-system/components/slider/score-slider'
import { useState } from 'react'
import { STRING, translate } from 'utils/language'
import { useUserPreferences } from 'utils/userPreferences/userPreferencesContext'

export const ThresholdSlider = () => {
  const { userPreferences, setUserPreferences } = useUserPreferences()
  const [displayThreshold, setDisplayThreshold] = useState(
    userPreferences.scoreThreshold
  )

  return (
    <ScoreSlider
      defaultValue={userPreferences.scoreThreshold}
      label={translate(STRING.FIELD_LABEL_SCORE)}
      value={displayThreshold}
      onValueChange={setDisplayThreshold}
      onValueCommit={(value) => {
        setDisplayThreshold(value)
        setUserPreferences({
          ...userPreferences,
          scoreThreshold: value,
        })
      }}
    />
  )
}
