import { API_ROUTES } from 'data-services/constants'
import { useStorageSources } from 'data-services/hooks/storage-sources/useStorageSources'
import { PageHeader } from 'design-system/components/page-header/page-header'
import { PaginationBar } from 'design-system/components/pagination-bar/pagination-bar'
import { Table } from 'design-system/components/table/table/table'
import { TableSortSettings } from 'design-system/components/table/types'
import { NewEntityDialog } from 'pages/project/entities/new-entity-dialog'
import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { DOCS_LINKS } from 'utils/constants'
import { STRING, translate } from 'utils/language'
import { usePagination } from 'utils/usePagination'
import { UserPermission } from 'utils/user/types'
import { columns } from './storage-columns'

export const Storage = () => {
  const { projectId } = useParams()
  const [sort, setSort] = useState<TableSortSettings | undefined>({
    field: 'created_at',
    order: 'desc',
  })
  const { pagination, setPage } = usePagination()
  const { items, userPermissions, total, isLoading, isFetching, error } =
    useStorageSources({
      projectId,
      pagination,
      sort,
    })
  const canCreate = userPermissions?.includes(UserPermission.Create)

  return (
    <>
      <PageHeader
        docsLink={DOCS_LINKS.CONFIGURING_DATA_SOURCE}
        isFetching={isFetching}
        isLoading={isLoading}
        subTitle={translate(STRING.RESULTS, { total })}
        title={translate(STRING.NAV_ITEM_STORAGE)}
        tooltip={translate(STRING.TOOLTIP_STORAGE)}
      >
        {canCreate && (
          <NewEntityDialog collection={API_ROUTES.STORAGE} type="storage" />
        )}
      </PageHeader>
      <Table
        columns={columns(projectId as string)}
        error={error}
        isLoading={isLoading}
        items={items}
        onSortSettingsChange={setSort}
        sortable
        sortSettings={sort}
      />
      {items?.length ? (
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
