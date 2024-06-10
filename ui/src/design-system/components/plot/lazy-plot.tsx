import { ErrorBoundary } from 'components/error-boundary/error-boundary'
import React, { Suspense } from 'react'
import { LoadingSpinner } from '../loading-spinner/loading-spinner'
import { PlotProps } from './types'

const _Plot = React.lazy(() => import('./plot'))

export const Plot = (props: PlotProps) => (
  <Suspense fallback={<LoadingSpinner />}>
    <ErrorBoundary>
      <_Plot {...props} />
    </ErrorBoundary>
  </Suspense>
)
