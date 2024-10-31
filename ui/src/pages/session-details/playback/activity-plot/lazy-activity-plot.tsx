import { ErrorBoundary } from 'components/error-boundary/error-boundary'
import { LoadingSpinner } from 'design-system/components/loading-spinner/loading-spinner'
import React, { Suspense } from 'react'
import { ActivityPlotProps } from './types'

const _ActivityPlot = React.lazy(() => import('./activity-plot'))

export const ActivityPlot = (props: ActivityPlotProps) => (
  <Suspense fallback={<LoadingSpinner />}>
    <ErrorBoundary>
      <_ActivityPlot {...props} />
    </ErrorBoundary>
  </Suspense>
)
