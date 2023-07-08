import { FetchInfo } from 'components/fetch-info/fetch-info'
import { useSessionDetails } from 'data-services/hooks/useSessionDetails'
import { LoadingSpinner } from 'design-system/components/loading-spinner/loading-spinner'
import { Plot } from 'design-system/components/plot/plot'
import { Error } from 'pages/error/error'
import { useContext, useEffect } from 'react'
import { useLocation, useParams } from 'react-router'
import { BreadcrumbContext } from 'utils/breadcrumbContext'
import { Playback } from './playback/playback'
import { useActiveOccurrences } from './playback/useActiveOccurrences'
import styles from './session-details.module.scss'
import { SessionInfo } from './session-info/session-info'

export const SessionDetails = () => {
  const location = useLocation()
  const { id } = useParams()
  const { setDetailBreadcrumb } = useContext(BreadcrumbContext)
  const { activeOccurrences } = useActiveOccurrences()
  const { session, isLoading, isFetching, error } = useSessionDetails(
    id as string,
    activeOccurrences[0]
  )

  useEffect(() => {
    setDetailBreadcrumb({
      title: session?.label ?? '',
      path: location.pathname,
    })

    return () => {
      setDetailBreadcrumb(undefined)
    }
  }, [session, location.pathname])

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
          <div className={styles.detailsContainer}>
            <div className={styles.detailsContent}>
              <Plot
                key={index}
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
