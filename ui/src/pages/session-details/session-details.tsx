import { FetchInfo } from 'components/fetch-info/fetch-info'
import { useSessionDetails } from 'data-services/hooks/useSessionDetails'
import { LoadingSpinner } from 'design-system/components/loading-spinner/loading-spinner'
import { Error } from 'pages/error/error'
import { useContext, useEffect } from 'react'
import { useLocation, useParams } from 'react-router'
import { BreadcrumbContext } from 'utils/breadcrumbContext'
import { Playback } from './playback/playback'
import styles from './session-details.module.scss'
import { SessionInfo } from './session-info/session-info'

export const SessionDetails = () => {
  const location = useLocation()
  const { id } = useParams()
  const { setDetailBreadcrumb } = useContext(BreadcrumbContext)
  const { session, isLoading, isFetching, error } = useSessionDetails(
    id as string
  )

  useEffect(() => {
    setDetailBreadcrumb({ title: `Session #${id}`, path: location.pathname })

    return () => {
      setDetailBreadcrumb(undefined)
    }
  }, [location.pathname])

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
    <>
      <div className={styles.main}>
        {isFetching && (
          <div className={styles.fetchInfoWrapper}>
            <FetchInfo isLoading={isLoading} />
          </div>
        )}
        <div className={styles.container}>
          <div className={styles.content}>
            <div className={styles.info}>
              <SessionInfo session={session} />
            </div>
          </div>
          <div className={styles.playback}>
            <Playback />
          </div>
        </div>
      </div>
      <div className={styles.graphs}>
        <div className={styles.container}>
          <div className={styles.content}>
            <span>WIP</span>
          </div>
        </div>
        <div className={styles.container}>
          <div className={styles.content}>
            <span>WIP</span>
          </div>
        </div>
        <div className={styles.container}>
          <div className={styles.content}>
            <span>WIP</span>
          </div>
        </div>
        <div className={styles.container}>
          <div className={styles.content}>
            <span>WIP</span>
          </div>
        </div>
      </div>
    </>
  )
}
