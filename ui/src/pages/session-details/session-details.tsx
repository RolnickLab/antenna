import { FetchInfo } from 'components/fetch-info/fetch-info'
import { useSessionDetails } from 'data-services/hooks/sessions/useSessionDetails'
import { LoadingSpinner } from 'design-system/components/loading-spinner/loading-spinner'
import { Plot } from 'design-system/components/plot/plot'
import { Error } from 'pages/error/error'
import { useContext, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { BreadcrumbContext } from 'utils/breadcrumbContext'
import { APP_ROUTES } from 'utils/constants'
import { Playback } from './playback/playback'
import { useActiveCaptureId } from './playback/useActiveCapture'
import { useActiveOccurrences } from './playback/useActiveOccurrences'
import styles from './session-details.module.scss'
import { SessionInfo } from './session-info/session-info'

export const SessionDetails = () => {
  const { projectId, id } = useParams()
  const { setDetailBreadcrumb } = useContext(BreadcrumbContext)
  const { activeOccurrences } = useActiveOccurrences()
  const { activeCaptureId } = useActiveCaptureId()
  const { session, isLoading, isFetching, error } = useSessionDetails(
    id as string,
    { capture: activeCaptureId, occurrence: activeOccurrences[0] }
  )

  useEffect(() => {
    setDetailBreadcrumb({
      title: session?.label ?? '',
      path: APP_ROUTES.SESSION_DETAILS({
        projectId: projectId as string,
        sessionId: id as string,
      }),
    })

    return () => {
      setDetailBreadcrumb(undefined)
    }
  }, [session])

  if (isLoading) {
    return (
      <div className={styles.loadingWrapper}>
        <LoadingSpinner />
      </div>
    )
  }

  if (!session || error) {
    return <Error />
  }

  return (
    <div className={styles.main}>
      {isFetching && (
        <div className={styles.fetchInfoWrapper}>
          <FetchInfo isLoading={isLoading} />
        </div>
      )}
      <div className={styles.playbackWrapper}>
        <Playback session={session} />
      </div>
      <div className={styles.details}>
        <div className={styles.detailsContainer}>
          <div className={styles.detailsContent}>
            <div className={styles.sessionInfo}>
              <SessionInfo session={session} />
            </div>
          </div>
        </div>
        {session.summaryData.map((summary, index) => (
          <div key={index} className={styles.detailsContainer}>
            <div className={styles.detailsContent}>
              <Plot
                title={summary.title}
                data={summary.data}
                orientation={summary.orientation}
                type={summary.type}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
