import { DefaultFiltersControl } from 'components/filtering/default-filter-control'
import { FilterControl } from 'components/filtering/filter-control'
import { FilterSection } from 'components/filtering/filter-section'
import { someActive } from 'components/filtering/utils'
import { useOccurrences } from 'data-services/hooks/occurrences/useOccurrences'
import { useTaxaLists } from 'data-services/hooks/taxa-lists/useTaxaLists'
import { DownloadIcon, Grid2X2Icon, TableIcon } from 'lucide-react'
import {
  BulkActionBar,
  buttonVariants,
  ColumnSettings,
  PageFooter,
  PageHeader,
  PaginationBar,
  SortControl,
  Table,
  ToggleGroup,
} from 'nova-ui-kit'
import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { APP_ROUTES, DOCS_LINKS } from 'utils/constants'
import { getAppRoute } from 'utils/getAppRoute'
import { STRING, translate } from 'utils/language'
import { useColumnSettings } from 'utils/useColumnSettings'
import { useFilters } from 'utils/useFilters'
import { usePagination } from 'utils/usePagination'
import { useUser } from 'utils/user/userContext'
import { useSelectedView } from 'utils/useSelectedView'
import { useSort } from 'utils/useSort'
import { columns } from './occurrence-columns'
import { OccurrenceDetailsDialog } from './occurrence-details-dialog'
import { OccurrenceGallery } from './occurrence-gallery'
import { OccurrencesActions } from './occurrences-actions'

export const Occurrences = () => {
  const { user } = useUser()
  const navigate = useNavigate()
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
  const tableColumns = columns({
    projectId: projectId as string,
    showActions: selectedItems.length === 0,
  })

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
            title={translate(STRING.MORE_FILTERS)}
            defaultOpen={someActive(
              [
                'collection',
                'deployment',
                'deployment__device',
                'deployment__research_site',
                'algorithm',
                'not_algorithm',
              ],
              activeFilters
            )}
          >
            <FilterControl field="date_start" />
            <FilterControl field="date_end" />
            <FilterControl field="collection" />
            <FilterControl field="deployment" />
            <FilterControl field="deployment__device" />
            <FilterControl field="deployment__research_site" />
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
                  Icon: TableIcon,
                },
                {
                  value: 'gallery',
                  label: translate(STRING.TAB_ITEM_GALLERY),
                  Icon: Grid2X2Icon,
                },
              ]}
              value={selectedView}
              onValueChange={setSelectedView}
            />
            <Link
              className={buttonVariants({ size: 'small', variant: 'outline' })}
              to={APP_ROUTES.EXPORTS({ projectId: projectId as string })}
            >
              <DownloadIcon className="w-4 h-4" />
              <span>Export</span>
            </Link>
            <SortControl columns={tableColumns} setSort={setSort} sort={sort} />
            <ColumnSettings
              columns={tableColumns}
              columnSettings={columnSettings}
              onColumnSettingsChange={setColumnSettings}
            />
          </PageHeader>
          {selectedView === 'table' && (
            <Table
              columns={tableColumns.filter(
                (column) => !!columnSettings[column.id]
              )}
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
            <OccurrencesActions
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
        <OccurrenceDetailsDialog
          id={id}
          occurrences={occurrences}
          onClose={() =>
            navigate(
              getAppRoute({
                to: APP_ROUTES.OCCURRENCES({ projectId: projectId as string }),
                keepSearchParams: true,
              })
            )
          }
        />
      ) : null}
    </>
  )
}
