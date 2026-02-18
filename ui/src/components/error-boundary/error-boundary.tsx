import * as Sentry from '@sentry/browser'
import { AlertTriangle } from 'lucide-react'
import { ReactNode } from 'react'
import { ErrorBoundary as _ErrorBoundary } from 'react-error-boundary'

const logErrorToService = (error: Error, errorInfo: any) => {
  const sentryEnabled = !!Sentry.getCurrentHub().getClient()

  if (!sentryEnabled) {
    return
  }

  Sentry.withScope((scope) => {
    scope.setExtras(errorInfo)
    Sentry.captureException(error)
  })
}

const FallbackComponent = ({ error }: { error: { message: string } }) => (
  <div className="w-full overflow-hidden flex flex-col items-center gap-4 p-8 text-center">
    <AlertTriangle className="w-6 h-6 text-destructive" />
    <p className="body-large">Something went wrong!</p>
    <p className="font-mono text-xs text-muted-foreground">{error.message}</p>
  </div>
)

export const ErrorBoundary = ({ children }: { children: ReactNode }) => (
  <_ErrorBoundary
    FallbackComponent={FallbackComponent}
    onError={logErrorToService}
  >
    {children}
  </_ErrorBoundary>
)
