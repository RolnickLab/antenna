import * as _Slider from '@radix-ui/react-slider'
import React, { useState } from 'react'
import styles from './slider.module.scss'

interface SliderProps {
  label: string
  description: string
  settings?: {
    min: number
    max: number
    step: number
    defaultValue: number
  }
}

export const Slider = ({
  label,
  description,
  settings = { min: 0, max: 1, step: 0.01, defaultValue: 0.5 },
}: SliderProps) => {
  const [value, setValue] = useState<number>(settings.defaultValue)

  return (
    <div>
      <label className={styles.label}>{label}</label>
      <_Slider.Root
        className={styles.sliderRoot}
        defaultValue={[settings.defaultValue]}
        min={settings.min}
        max={settings.max}
        step={settings.step}
        onValueChange={(values) => setValue(values[0])}
      >
        <_Slider.Track className={styles.sliderTrack}>
          <_Slider.Range className={styles.sliderRange} />
        </_Slider.Track>
        <_Slider.Thumb className={styles.sliderThumb}>
          <span className={styles.sliderValue}>{value}</span>
        </_Slider.Thumb>
      </_Slider.Root>
      <span className={styles.description}>{description}</span>
    </div>
  )
}
