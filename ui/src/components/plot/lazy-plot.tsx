import { ErrorBoundary } from 'components/error-boundary/error-boundary'
import { LoadingSpinner } from 'nova-ui-kit'
import React, { Suspense } from 'react'
import { PlotProps } from './types'

const _Plot = React.lazy(() => import('./plot'))

export const Plot = (props: PlotProps) => (
  <Suspense fallback={<LoadingSpinner />}>
    <ErrorBoundary>
      <_Plot {...props} />
    </ErrorBoundary>
  </Suspense>
)
