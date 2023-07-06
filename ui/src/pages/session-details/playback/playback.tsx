import { useInfiniteCaptures } from 'data-services/hooks/useInfiniteCaptures'
import { Capture } from 'data-services/models/capture'
import { SessionDetails } from 'data-services/models/session-details'
import { useEffect, useState } from 'react'
import { CapturePicker } from './capture-picker/capture-picker'
import { Frame } from './frame/frame'
import styles from './playback.module.scss'

export const Playback = ({ session }: { session: SessionDetails }) => {
  const {
    captures = [],
    hasNextPage,
    isLoading,
    fetchNextPage,
  } = useInfiniteCaptures(session.id)
  const [activeCapture, setActiveCapture] = useState<Capture>()
  const [showOverlay, setShowOverlay] = useState(false)

  useEffect(() => {
    if (!activeCapture && captures.length) {
      setActiveCapture(captures[0])
    }
  }, [captures])

  return (
    <div className={styles.wrapper}>
      <div
        className={styles.playbackFrame}
        onMouseOver={() => setShowOverlay(true)}
        onMouseOut={() => setShowOverlay(false)}
      >
        <Frame
          src={activeCapture?.src}
          width={activeCapture?.width ?? session.firstCapture.width}
          height={activeCapture?.height ?? session.firstCapture.height}
          detections={activeCapture?.detections ?? []}
          showOverlay={showOverlay}
        />
      </div>

      <div className={styles.capturePicker}>
        <CapturePicker
          activeCaptureId={activeCapture?.id}
          captures={captures}
          hasMore={hasNextPage}
          isLoading={isLoading}
          onNext={fetchNextPage}
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
