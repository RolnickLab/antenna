import { useInfiniteCaptures } from 'data-services/hooks/sessions/useInfiniteCaptures'
import { SessionDetails } from 'data-services/models/session-details'
import { useState } from 'react'
import { CapturePicker } from './capture-picker/capture-picker'
import { Frame } from './frame/frame'
import { PlaybackControls } from './playback-controls/playback-controls'
import styles from './playback.module.scss'
import { useActiveCapture } from './useActiveCapture'

export const Playback = ({ session }: { session: SessionDetails }) => {
  const {
    captures = [],
    fetchNextPage,
    fetchPreviousPage,
    isFetchingNextPage,
    isFetchingPreviousPage,
    hasNextPage,
    hasPreviousPage,
  } = useInfiniteCaptures(session.id, session.captureOffset)
  const { activeCapture, setActiveCapture } = useActiveCapture(captures)
  const [showOverlay, setShowOverlay] = useState(false)

  if (!session.firstCapture) {
    return null
  }

  return (
    <div className={styles.wrapper}>
      <div className={styles.playbackFrame}>
        <div
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
        <PlaybackControls activeCapture={activeCapture} session={session} />
      </div>

      <div className={styles.capturePicker}>
        <CapturePicker
          activeCaptureId={activeCapture?.id}
          captures={captures}
          detectionsMaxCount={session.detectionsMaxCount}
          hasNext={hasNextPage}
          hasPrev={hasPreviousPage}
          isLoadingNext={isFetchingNextPage}
          isLoadingPrev={isFetchingPreviousPage}
          onNext={fetchNextPage}
          onPrev={fetchPreviousPage}
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
