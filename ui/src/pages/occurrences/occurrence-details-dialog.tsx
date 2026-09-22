import { useOccurrenceDetails } from 'data-services/hooks/occurrences/useOccurrenceDetails'
import { Dialog } from 'nova-ui-kit'
import {
  OccurrenceDetails,
  TABS,
} from 'pages/occurrence-details/occurrence-details'
import { useContext, useEffect } from 'react'
import { useLocation } from 'react-router-dom'
import { BreadcrumbContext } from 'utils/breadcrumbContext'
import { STRING, translate } from 'utils/language'
import { useSelectedView } from 'utils/useSelectedView'
import { OccurrenceNavigation } from './occurrence-navigation'

// Occurrence identification modal. Rendered over a list (occurrences or taxa);
// the parent owns which occurrence is shown and how closing updates the URL.
export const OccurrenceDetailsDialog = ({
  id,
  occurrences,
  onClose,
  onNavigate,
  defaultTab = TABS.FIELDS,
}: {
  id: string
  // Ordered items the prev/next buttons page through. Only the id is used.
  occurrences?: { id: string }[]
  onClose: () => void
  // How prev/next switches occurrence. When omitted, navigation routes to the
  // occurrence detail page; the taxa list passes this to swap ?verifyOccurrence in place.
  onNavigate?: (id: string) => void
  // Tab to open on when no ?tab= is set. The taxa list opens on Identification so
  // verifying is the immediate action; the occurrences list keeps Fields.
  defaultTab?: string
}) => {
  const { state } = useLocation()
  const { selectedView, setSelectedView } = useSelectedView(defaultTab, 'tab')
  const { setDetailBreadcrumb } = useContext(BreadcrumbContext)
  const { occurrence, isLoading, error } = useOccurrenceDetails(id)

  useEffect(() => {
    // If a default tab is set from router state, set this as active
    if (state?.defaultTab) {
      setSelectedView(state.defaultTab)
    }
  }, [state?.defaultTab])

  useEffect(() => {
    setDetailBreadcrumb(
      occurrence ? { title: occurrence.displayName } : undefined
    )

    return () => {
      setDetailBreadcrumb(undefined)
    }
  }, [occurrence])

  return (
    <Dialog.Root
      open={!!id}
      onOpenChange={(open) => {
        if (!open) {
          setSelectedView(undefined)
          onClose()
        }
      }}
    >
      <Dialog.Content
        ariaCloselabel={translate(STRING.CLOSE)}
        error={error}
        isLoading={isLoading}
      >
        {occurrence ? (
          <OccurrenceDetails
            occurrence={occurrence}
            selectedTab={selectedView}
            setSelectedTab={setSelectedView}
          />
        ) : null}
        <OccurrenceNavigation
          occurrences={occurrences}
          currentId={id}
          onNavigate={onNavigate}
        />
      </Dialog.Content>
    </Dialog.Root>
  )
}
