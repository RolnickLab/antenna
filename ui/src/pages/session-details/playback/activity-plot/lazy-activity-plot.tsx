import { ErrorBoundary } from 'components/error-boundary/error-boundary'
import { LoadingSpinner } from 'design-system/components/loading-spinner/loading-spinner'
import React, { Suspense } from 'react'
import styles from './lazy-activity-plot.module.scss'
import { ActivityPlotProps } from './types'

const _ActivityPlot = React.lazy(() => import('./activity-plot'))

export const ActivityPlot = (props: ActivityPlotProps) => (
  <Suspense
    fallback={
      <div className={styles.loadingWrapper}>
        <LoadingSpinner size={32} />
      </div>
    }
  >
    <ErrorBoundary>
      <_ActivityPlot {...props} />
    </ErrorBoundary>
  </Suspense>
)
