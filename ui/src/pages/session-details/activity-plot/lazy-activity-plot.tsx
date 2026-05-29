import { ErrorBoundary } from 'components/error-boundary/error-boundary'
import { LoadingSpinner } from 'nova-ui-kit'
import React, { Suspense } from 'react'
import { ActivityPlotProps } from './activity-plot'

const _ActivityPlot = React.lazy(() => import('./activity-plot'))

export const ActivityPlot = (props: ActivityPlotProps) => (
  <Suspense
    fallback={
      <div>
        <LoadingSpinner size={32} />
      </div>
    }
  >
    <ErrorBoundary>
      <_ActivityPlot {...props} />
    </ErrorBoundary>
  </Suspense>
)
