import * as _Slider from '@radix-ui/react-slider'
import Dial from './dial.svg?react'
import styles from './styles.module.scss'

interface TimestampSliderProps {
  labels: string[]
  value: number
  onValueChange: (value: number) => void
}

export const TimestampSlider = ({
  labels,
  value,
  onValueChange,
}: TimestampSliderProps) => (
  <div className={styles.timestampSlider}>
    <_Slider.Root
      className={styles.sliderRoot}
      min={0}
      max={100}
      step={1}
      value={[value]}
      onValueChange={(values) => onValueChange(values[0])}
    >
      <_Slider.Track className={styles.sliderTrack}>
        <_Slider.Range className={styles.sliderRange} />
      </_Slider.Track>
      <_Slider.Thumb className={styles.sliderThumb}>
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
