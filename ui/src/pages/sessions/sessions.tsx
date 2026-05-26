import { FilterControl } from 'components/filtering/filter-control'
import { FilterSection } from 'components/filtering/filter-section'
import { useSessions } from 'data-services/hooks/sessions/useSessions'
import {
  ColumnSettings,
  PageFooter,
  PageHeader,
  PaginationBar,
  SortControl,
  Table,
  ToggleGroup,
} from 'design-system'
import { Grid2X2Icon, TableIcon } from 'lucide-react'
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
  const tableColumns = columns({ projectId: projectId as string })

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
            <SortControl columns={tableColumns} setSort={setSort} sort={sort} />
            <ColumnSettings
              columns={tableColumns}
              columnSettings={columnSettings}
              onColumnSettingsChange={setColumnSettings}
            />
          </PageHeader>
          {selectedView === 'table' && (
            <Table
              error={error}
              items={sessions}
              isLoading={isLoading}
              columns={tableColumns.filter(
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
