import { ScoreSlider } from 'design-system/components/slider/score-slider'
import { useState } from 'react'
import { STRING, translate } from 'utils/language'
import { useThreshold } from 'utils/threshold/thresholdContext'

export const ThresholdSlider = () => {
  const { defaultThreshold, threshold, setThreshold } = useThreshold()
  const [displayThreshold, setDisplayThreshold] = useState(threshold)

  return (
    <ScoreSlider
      defaultValue={defaultThreshold}
      label={translate(STRING.FIELD_LABEL_SCORE)}
      value={displayThreshold}
      onValueChange={setDisplayThreshold}
      onValueCommit={(value) => {
        setDisplayThreshold(value)
        setThreshold(value)
      }}
    />
  )
}
