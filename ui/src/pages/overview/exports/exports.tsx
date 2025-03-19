import { API_ROUTES } from 'data-services/constants'
import { useExports } from 'data-services/hooks/exports/useExports'
import { PageHeader } from 'design-system/components/page-header/page-header'
import { PaginationBar } from 'design-system/components/pagination-bar/pagination-bar'
import { Table } from 'design-system/components/table/table/table'
import { TableSortSettings } from 'design-system/components/table/types'
import { NewEntityDialog } from 'pages/overview/entities/new-entity-dialog'
import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { STRING, translate } from 'utils/language'
import { usePagination } from 'utils/usePagination'
import { UserPermission } from 'utils/user/types'
import { columns } from './exports-columns'

export const Exports = () => {
  const { projectId } = useParams()
  const [sort, setSort] = useState<TableSortSettings | undefined>({
    field: 'id',
    order: 'asc',
  })
  const { pagination, setPage } = usePagination()
  const { exports, userPermissions, total, isLoading, isFetching, error } =
    useExports({
      projectId,
      pagination,
      sort,
    })
  const canCreate = userPermissions?.includes(UserPermission.Create)

  return (
    <>
      <PageHeader
        title={translate(STRING.NAV_ITEM_EXPORTS)}
        subTitle={translate(STRING.RESULTS, {
          total,
        })}
        isLoading={isLoading}
        isFetching={isFetching}
      >
        {canCreate && (
          <NewEntityDialog collection={API_ROUTES.EXPORTS} type="export" />
        )}
      </PageHeader>
      <Table
        columns={columns(projectId as string)}
        error={error}
        isLoading={isLoading}
        items={exports}
        onSortSettingsChange={setSort}
        sortable
        sortSettings={sort}
      />
      {exports?.length ? (
        <PaginationBar
          pagination={pagination}
          total={total}
          setPage={setPage}
        />
      ) : null}
    </>
  )
}
