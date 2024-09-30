import { FetchInfo } from 'components/fetch-info/fetch-info'
import { useSessionDetails } from 'data-services/hooks/sessions/useSessionDetails'
import { Box } from 'design-system/components/box/box'
import { LoadingSpinner } from 'design-system/components/loading-spinner/loading-spinner'
import { PlotGrid } from 'design-system/components/plot-grid/plot-grid'
import { Plot } from 'design-system/components/plot/lazy-plot'
import { Error } from 'pages/error/error'
import { useContext, useEffect } from 'react'
import { Helmet } from 'react-helmet-async'
import { useParams } from 'react-router-dom'
import { BreadcrumbContext } from 'utils/breadcrumbContext'
import { Playback } from './playback/playback'
import { useActiveCaptureId } from './playback/useActiveCapture'
import { useActiveOccurrences } from './playback/useActiveOccurrences'
import styles from './session-details.module.scss'
import { SessionInfo } from './session-info/session-info'

export const SessionDetails = () => {
  const { id } = useParams()
  const { setDetailBreadcrumb } = useContext(BreadcrumbContext)
  const { activeOccurrences } = useActiveOccurrences()
  const { activeCaptureId } = useActiveCaptureId()
  const { session, isLoading, isFetching, error } = useSessionDetails(
    id as string,
    { capture: activeCaptureId, occurrence: activeOccurrences[0] }
  )

  useEffect(() => {
    setDetailBreadcrumb(session ? { title: session.label } : undefined)

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
    return <Error error={error} />
  }

  return (
    <div className={styles.main}>
      {session.exampleCaptures[0] && (
        <Helmet>
          <meta name="og:image" content={session.exampleCaptures[0].src} />
        </Helmet>
      )}
      {isFetching && (
        <div className={styles.fetchInfoWrapper}>
          <FetchInfo isLoading={isLoading} />
        </div>
      )}
      <div className={styles.playbackWrapper}>
        <Playback session={session} />
      </div>
      <PlotGrid>
        <Box>
          <div className={styles.sessionInfo}>
            <SessionInfo session={session} />
          </div>
        </Box>
        {session.summaryData.map((summary, index) => {
          if (summary.data.x.length <= 1) {
            return null
          }

          return (
            <Box key={index}>
              <Plot
                title={summary.title}
                data={summary.data}
                orientation={summary.orientation}
                type={summary.type}
              />
            </Box>
          )
        })}
      </PlotGrid>
    </div>
  )
}

export default SessionDetails
