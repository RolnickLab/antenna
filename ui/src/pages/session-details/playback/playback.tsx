import { useMemo, useState } from 'react'
import { CapturePicker } from './capture-picker/capture-picker'
import captures from './captures.json' // Only for testing
import { Frame } from './frame/frame'
import styles from './playback.module.scss'

export const Playback = () => {
  const [activeCaptureId, setActiveCaptureId] = useState(captures[0].id)
  const [showOverlay, setShowOverlay] = useState(false)
  const capture = captures.find((c) => c.id === activeCaptureId)

  const detections = useMemo(
    () => capture?.detections.filter((detection) => !!detection.label),
    [capture?.detections]
  )

  if (!capture) {
    return null
  }

  return (
    <div className={styles.wrapper}>
      <div
        className={styles.frameWrapper}
        onMouseOver={() => setShowOverlay(true)}
        onMouseOut={() => setShowOverlay(false)}
      >
        <Frame
          src={capture.source_image}
          width={capture.width}
          height={capture.height}
          detections={detections ?? []}
          showOverlay={showOverlay}
        />
      </div>

      <div className={styles.capturePicker}>
        <CapturePicker
          activeCaptureId={activeCaptureId}
          setActiveCaptureId={setActiveCaptureId}
        />
      </div>
    </div>
  )
}
