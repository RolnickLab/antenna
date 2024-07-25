import { FetchInfo } from 'components/fetch-info/fetch-info'
import { API_ROUTES } from 'data-services/constants'
import { useStorageSources } from 'data-services/hooks/storage-sources/useStorageSources'
import { PaginationBar } from 'design-system/components/pagination-bar/pagination-bar'
import { Table } from 'design-system/components/table/table/table'
import { TableSortSettings } from 'design-system/components/table/types'
import { Error } from 'pages/error/error'
import { NewEntityDialog } from 'pages/overview/entities/new-entity-dialog'
import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { usePagination } from 'utils/usePagination'
import { UserPermission } from 'utils/user/types'
import { columns } from './storage-columns'
import styles from './storage.module.scss'

export const StorageSources = () => {
  const { projectId } = useParams()
  const [sort, setSort] = useState<TableSortSettings>()
  const { pagination, setPage } = usePagination()
  const { items, userPermissions, total, isLoading, isFetching, error } =
    useStorageSources({
      projectId,
      pagination,
      sort,
    })
  const canCreate = userPermissions?.includes(UserPermission.Create)

  if (!isLoading && error) {
    return <Error />
  }

  return (
    <>
      {isFetching && (
        <div className={styles.fetchInfoWrapper}>
          <FetchInfo isLoading={isLoading} />
        </div>
      )}
      <Table
        items={items}
        isLoading={isLoading}
        columns={columns(projectId as string)}
        sortable
        sortSettings={sort}
        onSortSettingsChange={setSort}
      />
      {items?.length ? (
        <PaginationBar
          pagination={pagination}
          total={total}
          setPage={setPage}
        />
      ) : null}
      {canCreate && (
        <NewEntityDialog collection={API_ROUTES.STORAGE} type="storage" />
      )}
    </>
  )
}
