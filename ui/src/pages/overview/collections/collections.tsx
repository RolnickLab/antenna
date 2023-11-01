import { FetchInfo } from 'components/fetch-info/fetch-info'
import { useCollections } from 'data-services/hooks/collections/useCollections'
import { PaginationBar } from 'design-system/components/pagination-bar/pagination-bar'
import { Table } from 'design-system/components/table/table/table'
import { TableSortSettings } from 'design-system/components/table/types'
import { Error } from 'pages/error/error'
import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { usePagination } from 'utils/usePagination'
import { columns } from './collection-columns'
import styles from './collections.module.scss'

export const Collections = () => {
  const { projectId } = useParams()
  const [sort, setSort] = useState<TableSortSettings>()
  const { pagination, setPage } = usePagination()
  const { collections, total, isLoading, isFetching, error } = useCollections({
    projectId,
    pagination,
    sort,
  })

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
        items={collections}
        isLoading={isLoading}
        columns={columns(projectId as string)}
        sortable
        sortSettings={sort}
        onSortSettingsChange={setSort}
      />
      {collections?.length ? (
        <PaginationBar
          pagination={pagination}
          total={total}
          setPage={setPage}
        />
      ) : null}
    </>
  )
}
