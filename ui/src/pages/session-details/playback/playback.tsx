import {
  IconButton,
  IconButtonShape,
  IconButtonTheme,
} from 'design-system/components/icon-button/icon-button'
import { IconType } from 'design-system/components/icon/icon'
import { PlaybackSlider } from 'design-system/components/slider/slider'
import React, { useCallback, useEffect, useState } from 'react'
import captures from './captures.json' // Only for testing
import { Frame } from './frame/frame'
import styles from './playback.module.scss'

const MIN = 1
const MAX = captures.length
const DEFAULT_VALUE = 1

export const Playback = () => {
  const [frame, setFrame] = useState(DEFAULT_VALUE)
  const [tempFrame, setTempFrame] = useState(frame)

  const capture = captures[frame - 1]

  const setValidFrame = useCallback(
    (newFrame: number) => {
      const validFrame = Math.min(Math.max(newFrame, MIN), MAX)
      setFrame(validFrame)
    },
    [frame, setFrame]
  )

  useEffect(() => {
    setTempFrame(frame)
  }, [frame, setTempFrame])

  return (
    <div>
      <Frame
        src={capture.source_image}
        width={capture.width}
        height={capture.height}
        detections={capture.detections}
      />
      <div className={styles.controls}>
        <div className={styles.buttonWrapper}>
          <IconButton
            icon={IconType.ToggleLeft}
            shape={IconButtonShape.RoundLarge}
            theme={IconButtonTheme.Primary}
            onClick={() => setValidFrame(frame - 1)}
          />
          <IconButton
            icon={IconType.ToggleRight}
            shape={IconButtonShape.RoundLarge}
            theme={IconButtonTheme.Primary}
            onClick={() => setValidFrame(frame + 1)}
          />
        </div>
        <div style={{ flexGrow: 1 }}>
          <PlaybackSlider
            value={tempFrame}
            onValueChange={setTempFrame}
            onValueCommit={setFrame}
            settings={{
              min: MIN,
              max: MAX,
              step: 1,
              defaultValue: DEFAULT_VALUE,
            }}
          />
        </div>
      </div>
    </div>
  )
}
