import { useOccurrenceDetails } from 'data-services/hooks/occurrences/useOccurrenceDetails'
import _ from 'lodash'
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
import {
  OccurrenceNavigation,
  useOccurrenceNavigation,
} from './occurrence-navigation'
import { useAdvanceOnConfirm } from './use-advance-on-confirm'

// Occurrence identification modal. Rendered over a list (occurrences or taxa);
// the parent owns which occurrence is shown and how closing updates the URL.
export const OccurrenceDetailsDialog = ({
  advanceOnConfirm,
  id,
  occurrences,
  onClose,
  onNavigate,
  defaultTab = TABS.FIELDS,
}: {
  // Confirming the determination moves on to the next occurrence, or closes the
  // dialog after the last one, so reviewing a list is one click per occurrence.
  advanceOnConfirm?: boolean
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
  const navigation = useOccurrenceNavigation(occurrences, id, onNavigate)
  // Clears ?tab= too, so the next occurrence opened from the list starts on the default tab.
  const handleClose = () => {
    setSelectedView(undefined)
    onClose()
  }
  const advance = useAdvanceOnConfirm({
    close: handleClose,
    currentId: id,
    goTo: navigation.goTo,
    items: occurrences,
  })
  const detailsLabel = translate(STRING.ENTITY_DETAILS, {
    type: _.capitalize(translate(STRING.ENTITY_TYPE_OCCURRENCE)),
  })

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
          handleClose()
        }
      }}
    >
      <Dialog.Content
        ariaCloselabel={translate(STRING.CLOSE)}
        error={error}
        isLoading={isLoading}
      >
        <div className="sr-only">
          <Dialog.Header title={occurrence?.displayName ?? detailsLabel}>
            <Dialog.Description>{detailsLabel}</Dialog.Description>
          </Dialog.Header>
        </div>
        {occurrence ? (
          <OccurrenceDetails
            occurrence={occurrence}
            onConfirmed={advanceOnConfirm ? advance : undefined}
            selectedTab={selectedView}
            setSelectedTab={setSelectedView}
          />
        ) : null}
        <OccurrenceNavigation navigation={navigation} />
      </Dialog.Content>
    </Dialog.Root>
  )
}
