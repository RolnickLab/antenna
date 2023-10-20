import { SessionDetails } from 'data-services/models/session-details'
import { Button, ButtonTheme } from 'design-system/components/button/button'
import { IconType } from 'design-system/components/icon/icon'
import { PlaybackSlider } from 'design-system/components/slider/playback-slider'
import { useState } from 'react'
import styles from './playback-controls.module.scss'

const DEFAULT_VALUE = 0.6 // TODO: Current model should decide this value

export const PlaybackControls = ({ session }: { session: SessionDetails }) => {
  const [threshold, setThreshold] = useState(DEFAULT_VALUE)

  return (
    <div className={styles.controls}>
      <Button
        label="Process capture"
        theme={ButtonTheme.Neutral}
        icon={IconType.BatchId}
      />
      <div className={styles.slider}>
        {session.numDetections && session.numDetections > 0 ? (
          <PlaybackSlider
            defaultValue={DEFAULT_VALUE}
            label="Score"
            value={threshold}
            onValueChange={setThreshold}
            onValueCommit={setThreshold}
          />
        ) : null}
      </div>
    </div>
  )
}
