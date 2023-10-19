import { Button, ButtonTheme } from 'design-system/components/button/button'
import { IconType } from 'design-system/components/icon/icon'
import { PlaybackSlider } from 'design-system/components/slider/playback-slider'
import { useState } from 'react'
import styles from './playback-controls.module.scss'

const DEFAULT_VALUE = 0.6 // TODO: Current model should decide this value

export const PlaybackControls = () => {
  const [threshold, setThreshold] = useState(DEFAULT_VALUE)

  return (
    <div className={styles.controls}>
      <Button
        label="Process capture"
        theme={ButtonTheme.Neutral}
        icon={IconType.BatchId}
      />
      <div className={styles.slider}>
        <PlaybackSlider
          defaultValue={DEFAULT_VALUE}
          label="Confidence"
          value={threshold}
          onValueChange={setThreshold}
          onValueCommit={setThreshold}
        />
      </div>
    </div>
  )
}
