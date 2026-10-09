import { Slider } from 'nova-ui-kit'
import { useEffect, useState } from 'react'
import { STRING, translate } from 'utils/language'
import { FilterProps } from './types'

interface SliderScale {
  max: number
  step: number
  unit: string
  // Converts between the slider value and the query param value.
  toParam: (value: number) => number
  fromParam: (value: number) => number
}

const MM_SCALE: SliderScale = {
  max: 50,
  step: 1,
  unit: 'mm',
  toParam: (value) => value,
  fromParam: (value) => value,
}

// Relative sizes are a fraction of the capture's longest side, shown as a percentage.
const RELATIVE_SCALE: SliderScale = {
  max: 10,
  step: 0.1,
  unit: '%',
  toParam: (value) => Number((value / 100).toFixed(4)),
  fromParam: (value) => Number((value * 100).toFixed(1)),
}

const MinSizeSlider = ({
  onAdd,
  onClear,
  scale,
  value,
}: FilterProps & { scale: SliderScale }) => {
  const paramValue = value ? scale.fromParam(Number(value)) : 0
  const [sliderValue, setSliderValue] = useState(paramValue)

  useEffect(() => {
    setSliderValue(paramValue)
  }, [paramValue])

  return (
    <div className="w-full h-8 flex items-center gap-2">
      <Slider
        aria-label={translate(STRING.FIELD_LABEL_MIN_SIZE)}
        invertedColors
        max={scale.max}
        min={0}
        step={scale.step}
        value={[sliderValue]}
        onValueChange={([newValue]) => setSliderValue(newValue)}
        onValueCommit={([newValue]) => {
          if (newValue > 0) {
            onAdd(`${scale.toParam(newValue)}`)
          } else {
            onClear()
          }
        }}
      />
      <span className="w-16 shrink-0 text-right body-small text-muted-foreground">
        {sliderValue} {scale.unit}
      </span>
    </div>
  )
}

export const MinSizeMmFilter = (props: FilterProps) => (
  <MinSizeSlider {...props} scale={MM_SCALE} />
)

export const MinSizeRelativeFilter = (props: FilterProps) => (
  <MinSizeSlider {...props} scale={RELATIVE_SCALE} />
)
