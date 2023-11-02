import * as _Slider from '@radix-ui/react-slider'
import styles from './styles.module.scss'

interface SliderProps {
  description?: string
  label: string
  settings?: {
    min: number
    max: number
    step: number
  }
  value: number
  onValueChange: (value: number) => void
}

export const Slider = ({
  description,
  label,
  settings = { min: 0, max: 1, step: 0.01 },
  value,
  onValueChange,
}: SliderProps) => (
  <div>
    <label className={styles.label}>{label}</label>
    <_Slider.Root
      className={styles.sliderRoot}
      min={settings.min}
      max={settings.max}
      step={settings.step}
      value={[value]}
      onValueChange={(values) => onValueChange(values[0])}
    >
      <_Slider.Track className={styles.sliderTrack}>
        <_Slider.Range className={styles.sliderRange} />
      </_Slider.Track>
      <_Slider.Thumb className={styles.sliderThumb}>
        <span className={styles.sliderValue}>{value}</span>
      </_Slider.Thumb>
    </_Slider.Root>
    {description?.length && (
      <span className={styles.description}>{description}</span>
    )}
  </div>
)
