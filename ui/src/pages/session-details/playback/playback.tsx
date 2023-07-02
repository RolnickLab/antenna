import { useCaptures } from 'data-services/hooks/useCaptures'
import { Capture } from 'data-services/models/capture'
import { useEffect, useState } from 'react'
import { CapturePicker } from './capture-picker/capture-picker'
import { Frame } from './frame/frame'
import styles from './playback.module.scss'

export const Playback = ({ sessionId }: { sessionId: string }) => {
  const { captures = [] } = useCaptures(sessionId)
  const [activeCaptureId, setActiveCaptureId] = useState<string>()
  const [showOverlay, setShowOverlay] = useState(false)

  useEffect(() => {
    if (!activeCaptureId) {
      setActiveCaptureId(captures[0]?.id)
    }
  }, [captures])

  const capture = captures?.find((c) => c.id === activeCaptureId)

  if (!activeCaptureId || !capture) {
    return null
  }

  return (
    <div className={styles.wrapper}>
      <div
        className={styles.frameWrapper}
        onMouseOver={() => setShowOverlay(true)}
        onMouseOut={() => setShowOverlay(false)}
      >
        <PlaybackFrame capture={capture} showOverlay={showOverlay} />
      </div>

      <div className={styles.capturePicker}>
        <CapturePicker
          activeCaptureId={activeCaptureId}
          captures={captures}
          setActiveCaptureId={setActiveCaptureId}
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
  return (
    <Frame
      src={capture.src}
      width={capture.width}
      height={capture.height}
      detections={[]}
      showOverlay={showOverlay}
    />
  )
}
