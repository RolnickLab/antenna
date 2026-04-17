import { FilterControl } from 'components/filtering/filter-control'
import { FilterSection } from 'components/filtering/filter-section'
import { useSessions } from 'data-services/hooks/sessions/useSessions'
import { IconType } from 'design-system/components/icon/icon'
import { PageFooter } from 'design-system/components/page-footer/page-footer'
import { PageHeader } from 'design-system/components/page-header/page-header'
import { PaginationBar } from 'design-system/components/pagination-bar/pagination-bar'
import { SortControl } from 'design-system/components/sort-control'
import { ColumnSettings } from 'design-system/components/table/column-settings/column-settings'
import { Table } from 'design-system/components/table/table/table'
import { ToggleGroup } from 'design-system/components/toggle-group/toggle-group'
import { useParams } from 'react-router-dom'
import { STRING, translate } from 'utils/language'
import { useColumnSettings } from 'utils/useColumnSettings'
import { useFilters } from 'utils/useFilters'
import { usePagination } from 'utils/usePagination'
import { useSelectedView } from 'utils/useSelectedView'
import { useSort } from 'utils/useSort'
import { columns } from './session-columns'
import { SessionGallery } from './session-gallery'

export const Sessions = () => {
  const { projectId } = useParams()
  const { columnSettings, setColumnSettings } = useColumnSettings('sessions', {
    deployment: true,
    snapshots: true,
    session: true,
    images: true,
    duration: true,
    captures: true,
    occurrences: true,
    species: true,
  })
  const { sort, setSort } = useSort({
    field: 'occurrences_count',
    order: 'desc',
  })
  const { pagination, setPage } = usePagination()
  const { filters } = useFilters()
  const { sessions, total, isLoading, isFetching, error } = useSessions({
    projectId,
    sort,
    pagination,
    filters,
  })
  const { selectedView, setSelectedView } = useSelectedView('table')

  return (
    <>
      <div className="flex flex-col gap-6 md:flex-row">
        <FilterSection defaultOpen>
          <FilterControl field="deployment" />
        </FilterSection>
        <div className="w-full overflow-hidden">
          <PageHeader
            title={translate(STRING.NAV_ITEM_SESSIONS)}
            subTitle={translate(STRING.RESULTS, {
              total,
            })}
            isLoading={isLoading}
            isFetching={isFetching}
            tooltip={translate(STRING.TOOLTIP_SESSION)}
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
            <ColumnSettings
              columns={columns(projectId as string)}
              columnSettings={columnSettings}
              onColumnSettingsChange={setColumnSettings}
            />
          </PageHeader>
          {selectedView === 'table' && (
            <Table
              error={error}
              items={sessions}
              isLoading={isLoading}
              columns={columns(projectId as string).filter(
                (column) => !!columnSettings[column.id]
              )}
              sortable
              sortSettings={sort}
              onSortSettingsChange={setSort}
            />
          )}
          {selectedView === 'gallery' && (
            <SessionGallery
              error={error}
              isLoading={isLoading}
              sessions={sessions}
            />
          )}
        </div>
      </div>
      <PageFooter>
        {sessions?.length ? (
          <PaginationBar
            pagination={pagination}
            total={total}
            setPage={setPage}
          />
        ) : null}
      </PageFooter>
    </>
  )
}
