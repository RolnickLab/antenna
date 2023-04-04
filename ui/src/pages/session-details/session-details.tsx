import { useSessionDetails } from 'data-services/hooks/useSessionDetails'
import { LoadingSpinner } from 'design-system/components/loading-spinner/loading-spinner'
import React from 'react'
import { useParams } from 'react-router'
import { Playback } from './playback/playback'
import styles from './session-details.module.scss'
import { SessionInfo } from './session-info/session-info'

export const SessionDetails = () => {
  const { id } = useParams()
  const { session, isLoading } = useSessionDetails(id as string)

  if (isLoading) {
    return (
      <div className={styles.loadingWrapper}>
        <LoadingSpinner />
      </div>
    )
  }

  if (!session) {
    return null // TODO: Show error state
  }

  return (
    <>
      <div className={styles.main}>
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
