import { useCaptureDetails } from 'data-services/hooks/useCaptureDetails'
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
    return null
  }

  return (
    <div className={styles.wrapper}>
      <div
        className={styles.frameWrapper}
        onMouseOver={() => setShowOverlay(true)}
        onMouseOut={() => setShowOverlay(false)}
      >
        <PlaybackFrame capture={activeCapture} showOverlay={showOverlay} />
      </div>

      <div className={styles.capturePicker}>
        <CapturePicker
          activeCaptureId={activeCapture?.id}
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

const PlaybackFrame = ({
  capture,
  showOverlay,
}: {
  capture: Capture
  showOverlay: boolean
}) => {
  const { capture: captureDetails } = useCaptureDetails(capture.id)

  return (
    <Frame
      src={capture.src}
      width={capture.width}
      height={capture.height}
      detections={captureDetails?.detections ?? []}
      showOverlay={showOverlay}
    />
  )
}
