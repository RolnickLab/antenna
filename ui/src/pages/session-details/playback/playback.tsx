import { PlaybackSlider } from 'design-system/components/slider/slider'
import React from 'react'
import capture from './capture.json' // Only for testing
import { Frame } from './frame/frame'
import styles from './playback.module.scss'

export const Playback = () => (
  <div>
    <Frame
      src={capture.source_image}
      width={capture.width}
      height={capture.height}
      detections={capture.detections}
    />
    <div className={styles.controls}>
      <div style={{ width: '100%' }}>
        <PlaybackSlider
          settings={{ min: 1, max: 30, step: 1, defaultValue: 1 }}
        />
      </div>
    </div>
  </div>
)
