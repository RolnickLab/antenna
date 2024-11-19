import { Slider } from 'nova-ui-kit'
import { useState } from 'react'

interface ScoreSliderSliderProps {
  defaultValue: number
  label: string
  value: number
  onValueChange: (value: number) => void
  onValueCommit: (value: number) => void
}

export const ScoreSlider = ({
  defaultValue,
  label,
  value,
  onValueChange,
  onValueCommit,
}: ScoreSliderSliderProps) => {
  const [active, setActive] = useState(false)

  return (
    <div className="w-full h-12 flex items-center gap-4 text-generic-white">
      <span className="body-overline-small font-bold">{label}</span>
      <Slider
        invertedColors
        defaultValue={[defaultValue]}
        min={0}
        max={1}
        step={0.01}
        value={[value]}
        onValueChange={(values) => onValueChange(values[0])}
        onValueCommit={(values) => onValueCommit(values[0])}
        onPointerDown={() => setActive(true)}
        onPointerUp={() => setActive(false)}
        onPointerLeave={() => {
          if (active) {
            onValueCommit(value)
          }
        }}
      />
      <span className="w-12 text-right body-overline">{value}</span>
    </div>
  )
}
