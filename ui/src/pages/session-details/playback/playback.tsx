import { PlaybackSlider } from 'design-system/components/slider/slider'
import React from 'react'
import styles from './playback.module.scss'

export const Playback = () => (
  <div className={styles.wrapper}>
    <div className={styles.controls}>
      <div style={{ width: '100%' }}>
        <PlaybackSlider
          settings={{ min: 1, max: 30, step: 1, defaultValue: 1 }}
        />
      </div>
    </div>
  </div>
)
