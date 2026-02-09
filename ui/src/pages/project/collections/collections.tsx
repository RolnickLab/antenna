import { API_ROUTES } from 'data-services/constants'
import { useCollections } from 'data-services/hooks/collections/useCollections'
import { PageHeader } from 'design-system/components/page-header/page-header'
import { PaginationBar } from 'design-system/components/pagination-bar/pagination-bar'
import { ColumnSettings } from 'design-system/components/table/column-settings/column-settings'
import { Table } from 'design-system/components/table/table/table'
import { TableSortSettings } from 'design-system/components/table/types'
import { NewEntityDialog } from 'pages/project/entities/new-entity-dialog'
import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { STRING, translate } from 'utils/language'
import { useColumnSettings } from 'utils/useColumnSettings'
import { usePagination } from 'utils/usePagination'
import { UserPermission } from 'utils/user/types'
import { columns } from './collection-columns'

export const Collections = () => {
  const { projectId } = useParams()
  const [sort, setSort] = useState<TableSortSettings | undefined>({
    field: 'id',
    order: 'asc',
  })
  const { columnSettings, setColumnSettings } = useColumnSettings(
    'collections',
    {
      id: true,
      name: true,
      settings: true,
      captures: true,
      'captures-with-detections': true,
      status: true,
    }
  )
  const { pagination, setPage } = usePagination()
  const [poll, setPoll] = useState(false)
  const countColumnVisible = columnSettings.occurrences || columnSettings.taxa
  const sortByCountActive =
    sort?.field === 'occurrences_count' || sort?.field === 'taxa_count'
  const { collections, userPermissions, total, isLoading, isFetching, error } =
    useCollections(
      {
        projectId,
        pagination,
        sort,
        withCounts: countColumnVisible || sortByCountActive, // Only fetch counts if needed since counts will slow down the response
      },
      poll
    )
  const canCreate = userPermissions?.includes(UserPermission.Create)

  useEffect(() => {
    // If any collection has a job in progress, we want to poll the endpoint so we can show job updates
    if (collections?.some(({ hasJobInProgress }) => hasJobInProgress)) {
      setPoll(true)
    } else {
      setPoll(false)
    }
  }, [collections])

  return (
    <>
      <PageHeader
        title={translate(STRING.NAV_ITEM_CAPTURE_SETS)}
        subTitle={translate(STRING.RESULTS, {
          total,
        })}
        isLoading={isLoading}
        isFetching={isFetching}
        tooltip={translate(STRING.TOOLTIP_CAPTURE_SET)}
      >
        <ColumnSettings
          columns={columns(projectId as string)}
          columnSettings={columnSettings}
          onColumnSettingsChange={setColumnSettings}
        />
        {canCreate && (
          <NewEntityDialog
            collection={API_ROUTES.COLLECTIONS}
            type={translate(STRING.ENTITY_TYPE_CAPTURE_SET)}
          />
        )}
      </PageHeader>
      <Table
        columns={columns(projectId as string).filter((column) => {
          // Always show action column
          if (column.id === 'actions') {
            return true
          }

          return !!columnSettings[column.id]
        })}
        error={error}
        isLoading={isLoading}
        items={collections}
        onSortSettingsChange={setSort}
        sortable
        sortSettings={sort}
      />
      {collections?.length ? (
        <PaginationBar
          compact
          pagination={pagination}
          setPage={setPage}
          total={total}
        />
      ) : null}
    </>
  )
}
