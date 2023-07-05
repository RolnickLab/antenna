import { useCaptures } from 'data-services/hooks/useCaptures'
import { Capture } from 'data-services/models/capture'
import { useEffect, useState } from 'react'
import { CapturePicker } from './capture-picker/capture-picker'
import { Frame } from './frame/frame'
import styles from './playback.module.scss'

export const Playback = ({ sessionId }: { sessionId: string }) => {
  const { captures = [] } = useCaptures(sessionId)
  const [activeCapture, setActiveCapture] = useState<Capture>()
  const [showOverlay, setShowOverlay] = useState(false)

  useEffect(() => {
    if (!activeCapture && captures.length) {
      setActiveCapture(captures[0])
    }
  }, [captures])

  if (!activeCapture) {
    return null // TODO: Show loading spinner
  }

  return (
    <div className={styles.wrapper}>
      <div
        className={styles.playbackFrame}
        onMouseOver={() => setShowOverlay(true)}
        onMouseOut={() => setShowOverlay(false)}
      >
        <Frame
          src={activeCapture.src}
          width={activeCapture.width}
          height={activeCapture.height}
          detections={activeCapture.detections}
          showOverlay={showOverlay}
        />
      </div>

      <div className={styles.capturePicker}>
        <CapturePicker
          activeCaptureId={activeCapture.id}
          captures={captures}
          setActiveCaptureId={(captureId) => {
            const capture = captures.find((c) => c.id === captureId)
            if (capture) {
              setActiveCapture(capture)
            }
          }}
        />
      </div>
    </div>
  )
}
