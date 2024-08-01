import * as _Slider from '@radix-ui/react-slider'
import Dial from './dial.svg?react'
import styles from './styles.module.scss'

interface TimestampSliderProps {
  labels: string[]
  value: number
  valueLabel?: string
  onValueChange: (value: number) => void
  onValueCommit: (value: number) => void
}

export const TimestampSlider = ({
  labels,
  value,
  valueLabel,
  onValueChange,
  onValueCommit,
}: TimestampSliderProps) => (
  <div className={styles.timestampSlider}>
    <_Slider.Root
      className={styles.sliderRoot}
      min={0}
      max={100}
      step={0.01}
      value={[value]}
      onValueChange={(values) => onValueChange(values[0])}
      onValueCommit={(values) => onValueCommit(values[0])}
    >
      <_Slider.Track className={styles.sliderTrack}>
        <_Slider.Range className={styles.sliderRange} />
      </_Slider.Track>
      <_Slider.Thumb className={styles.sliderThumb}>
        {valueLabel && <span className={styles.label}>{valueLabel}</span>}
        <Dial />
      </_Slider.Thumb>
    </_Slider.Root>
    <div className={styles.labels}>
      {labels.map((label, index) => (
        <span key={index} className={styles.label}>
          {label}
        </span>
      ))}
    </div>
  </div>
)
