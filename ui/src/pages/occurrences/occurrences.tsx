import { DefaultFiltersControl } from 'components/filtering/default-filter-control'
import { FilterControl } from 'components/filtering/filter-control'
import { FilterSection } from 'components/filtering/filter-section'
import { someActive } from 'components/filtering/utils'
import { useOccurrenceDetails } from 'data-services/hooks/occurrences/useOccurrenceDetails'
import { useOccurrences } from 'data-services/hooks/occurrences/useOccurrences'
import { useTaxaLists } from 'data-services/hooks/taxa-lists/useTaxaLists'
import { Occurrence } from 'data-services/models/occurrence'
import { BulkActionBar } from 'design-system/components/bulk-action-bar/bulk-action-bar'
import * as Dialog from 'design-system/components/dialog/dialog'
import { IconType } from 'design-system/components/icon/icon'
import { PageFooter } from 'design-system/components/page-footer/page-footer'
import { PageHeader } from 'design-system/components/page-header/page-header'
import { PaginationBar } from 'design-system/components/pagination-bar/pagination-bar'
import { SortControl } from 'design-system/components/sort-control'
import { ColumnSettings } from 'design-system/components/table/column-settings/column-settings'
import { Table } from 'design-system/components/table/table/table'
import { ToggleGroup } from 'design-system/components/toggle-group/toggle-group'
import { DownloadIcon } from 'lucide-react'
import { buttonVariants } from 'nova-ui-kit'
import {
  OccurrenceDetails,
  TABS,
} from 'pages/occurrence-details/occurrence-details'
import { useContext, useEffect, useState } from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'
import { BreadcrumbContext } from 'utils/breadcrumbContext'
import { APP_ROUTES, DOCS_LINKS } from 'utils/constants'
import { getAppRoute } from 'utils/getAppRoute'
import { STRING, translate } from 'utils/language'
import { useColumnSettings } from 'utils/useColumnSettings'
import { useFilters } from 'utils/useFilters'
import { usePagination } from 'utils/usePagination'
import { useUser } from 'utils/user/userContext'
import { useSelectedView } from 'utils/useSelectedView'
import { useSort } from 'utils/useSort'
import { OccurrenceActions } from './occurrence-actions'
import { columns } from './occurrence-columns'
import { OccurrenceGallery } from './occurrence-gallery'
import { OccurrenceNavigation } from './occurrence-navigation'

export const Occurrences = () => {
  const { user } = useUser()
  const { projectId, id } = useParams()
  const { columnSettings, setColumnSettings } = useColumnSettings(
    'occurrences',
    {
      batch: true,
      snapshots: true,
      id: true,
      date: true,
      deployment: true,
      duration: false,
      detections: true,
      score: true,
      ['updated-at']: true,
    }
  )
  const { sort, setSort } = useSort({
    field: 'updated_at',
    order: 'desc',
  })
  const { pagination, setPage } = usePagination()
  const { activeFilters, filters } = useFilters()
  const { occurrences, total, isLoading, isFetching, error } = useOccurrences({
    projectId,
    pagination,
    sort,
    filters,
  })
  const [_selectedItems, setSelectedItems] = useState<string[]>([])
  const selectedItems = _selectedItems.filter((id) =>
    occurrences?.some((occurrence) => occurrence.id === id)
  )
  const { selectedView, setSelectedView } = useSelectedView('table')
  const { taxaLists = [] } = useTaxaLists({ projectId: projectId as string })

  useEffect(() => {
    document.getElementById('app')?.scrollTo({ top: 0 })
  }, [pagination.page])

  useEffect(() => {
    if (id) {
      document
        .getElementById(id)
        ?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
    }
  }, [id])

  return (
    <>
      <div className="flex flex-col gap-6 md:flex-row">
        <div className="space-y-6">
          <FilterSection defaultOpen>
            <FilterControl field="detections__source_image" readonly />
            <FilterControl field="event" readonly />
            <FilterControl field="taxon" />
            {taxaLists.length > 0 && (
              <>
                <FilterControl data={taxaLists} field="taxa_list_id" />
                <FilterControl data={taxaLists} field="not_taxa_list_id" />
              </>
            )}
            <FilterControl field="verified" />
            {user.loggedIn && <FilterControl field="verified_by_me" />}
            <DefaultFiltersControl field="apply_defaults" />
          </FilterSection>
          <FilterSection
            title="More filters"
            defaultOpen={someActive(
              ['collection', 'deployment', 'algorithm', 'not_algorithm'],
              activeFilters
            )}
          >
            <FilterControl field="date_start" />
            <FilterControl field="date_end" />
            <FilterControl field="collection" />
            <FilterControl field="deployment" />
            <FilterControl field="algorithm" />
            <FilterControl field="not_algorithm" />
          </FilterSection>
        </div>
        <div className="w-full overflow-hidden">
          <PageHeader
            docsLink={DOCS_LINKS.VALIDATING_DATA}
            isFetching={isFetching}
            isLoading={isLoading}
            subTitle={translate(STRING.RESULTS, { total })}
            title={translate(STRING.NAV_ITEM_OCCURRENCES)}
            tooltip={translate(STRING.TOOLTIP_OCCURRENCE)}
          >
            <ToggleGroup
              items={[
                {
                  value: 'table',
                  label: translate(STRING.TAB_ITEM_TABLE),
                  icon: IconType.TableView,
                },
                {
                  value: 'gallery',
                  label: translate(STRING.TAB_ITEM_GALLERY),
                  icon: IconType.GalleryView,
                },
              ]}
              value={selectedView}
              onValueChange={setSelectedView}
            />
            <SortControl
              columns={columns(projectId as string)}
              setSort={setSort}
              sort={sort}
            />
            <Link
              className={buttonVariants({ size: 'small', variant: 'outline' })}
              to={APP_ROUTES.EXPORTS({ projectId: projectId as string })}
            >
              <DownloadIcon className="w-4 h-4" />
              <span>Export </span>
            </Link>
            <ColumnSettings
              columns={columns(projectId as string)}
              columnSettings={columnSettings}
              onColumnSettingsChange={setColumnSettings}
            />
          </PageHeader>
          {selectedView === 'table' && (
            <Table
              columns={columns(
                projectId as string,
                selectedItems.length === 0
              ).filter((column) => !!columnSettings[column.id])}
              error={error}
              isLoading={!id && isLoading}
              items={occurrences}
              onSelectedItemsChange={setSelectedItems}
              onSortSettingsChange={setSort}
              selectable={user.loggedIn}
              selectedItems={selectedItems}
              sortable
              sortSettings={sort}
            />
          )}
          {selectedView === 'gallery' && (
            <OccurrenceGallery
              error={error}
              isLoading={!id && isLoading}
              items={occurrences}
              onSelectedItemsChange={setSelectedItems}
              selectable={user.loggedIn}
              selectedItems={selectedItems}
            />
          )}
        </div>
      </div>
      <PageFooter
        hide={
          selectedItems.length === 0 &&
          (!occurrences || occurrences.length === 0)
        }
      >
        {selectedItems.length ? (
          <BulkActionBar
            selectedItems={selectedItems.filter((id) =>
              occurrences?.some((occurrence) => occurrence.id === id)
            )}
            onClear={() => setSelectedItems([])}
          >
            <OccurrenceActions
              occurrences={occurrences?.filter((occurrence) =>
                selectedItems.includes(occurrence.id)
              )}
            />
          </BulkActionBar>
        ) : null}
        {occurrences?.length ? (
          <PaginationBar
            pagination={pagination}
            total={total}
            setPage={setPage}
          />
        ) : null}
      </PageFooter>
      {id ? (
        <OccurrenceDetailsDialog id={id} occurrences={occurrences} />
      ) : null}
    </>
  )
}

const OccurrenceDetailsDialog = ({
  id,
  occurrences,
}: {
  id: string
  occurrences?: Occurrence[]
}) => {
  const navigate = useNavigate()
  const { state } = useLocation()
  const { selectedView, setSelectedView } = useSelectedView(TABS.FIELDS, 'tab')
  const { projectId } = useParams()
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
        }

        navigate(
          getAppRoute({
            to: APP_ROUTES.OCCURRENCES({ projectId: projectId as string }),
            keepSearchParams: true,
          })
        )
      }}
    >
      <Dialog.Content
        ariaCloselabel={translate(STRING.CLOSE)}
        isLoading={isLoading}
        error={error}
      >
        {occurrence ? (
          <OccurrenceDetails
            occurrence={occurrence}
            selectedTab={selectedView}
            setSelectedTab={setSelectedView}
          />
        ) : null}
        <OccurrenceNavigation occurrences={occurrences} />
      </Dialog.Content>
    </Dialog.Root>
  )
}
