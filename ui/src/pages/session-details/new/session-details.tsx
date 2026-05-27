import { ErrorState } from 'components/error-state/error-state'
import { useSessionDetails } from 'data-services/hooks/sessions/useSessionDetails'
import { Box, LoadingSpinner, PageHeader, Tabs } from 'nova-ui-kit'
import { useContext, useEffect } from 'react'
import { Helmet } from 'react-helmet-async'
import { useParams } from 'react-router-dom'
import { BreadcrumbContext } from 'utils/breadcrumbContext'
import { STRING, translate } from 'utils/language'
import { useActiveCaptureId } from './hooks/useActiveCapture'
import { useActiveOccurrences } from './hooks/useActiveOccurrences'
import { SessionInfo } from './session-info'
import { SessionPlots } from './session-plots'

const TABS = {
  FIELDS: 'fields',
  CHARTS: 'charts',
}

export const SessionDetails = () => {
  const { id } = useParams()
  const { setDetailBreadcrumb } = useContext(BreadcrumbContext)
  const { activeOccurrences } = useActiveOccurrences()
  const { activeCaptureId } = useActiveCaptureId()
  const { session, isLoading, error } = useSessionDetails(id as string, {
    capture: activeCaptureId,
    occurrence: activeOccurrences[0],
  })

  useEffect(() => {
    setDetailBreadcrumb(session ? { title: session.label } : undefined)

    return () => {
      setDetailBreadcrumb(undefined)
    }
  }, [session])

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[320px]">
        <LoadingSpinner />
      </div>
    )
  }

  if (!session || error) {
    return <ErrorState error={error} />
  }

  return (
    <>
      <Helmet>
        <meta name="og:image" content={session.exampleCaptures[0]?.src} />
      </Helmet>
      <PageHeader
        title={session.label}
        subTitle={translate(STRING.RESULTS_CAPTURES, {
          total: session?.numImages ?? 0,
        })}
        isLoading={isLoading}
        tooltip={translate(STRING.TOOLTIP_SESSION)}
      />
      <div className="flex flex-col gap-6 mt-6 md:flex-row">
        <Box className="p-2 bg-background rounded-lg md:min-w-72 md:p-4 md:rounded-xl">
          <Tabs.Root defaultValue={TABS.FIELDS}>
            <Tabs.List>
              <Tabs.Trigger
                value={TABS.FIELDS}
                label={translate(STRING.TAB_ITEM_FIELDS)}
              />
              <Tabs.Trigger
                value={TABS.CHARTS}
                label={translate(STRING.TAB_ITEM_CHARTS)}
              />
            </Tabs.List>
            <Tabs.Content value={TABS.FIELDS}>
              <SessionInfo session={session} />
            </Tabs.Content>
            <Tabs.Content value={TABS.CHARTS}>
              <div className="w-96 space-y-4">
                <SessionPlots session={session} />
              </div>
            </Tabs.Content>
          </Tabs.Root>
        </Box>
        <div className="grow rounded-lg aspect-video border border-border md:rounded-xl">
          <></>
        </div>
      </div>
    </>
  )
}

export default SessionDetails
