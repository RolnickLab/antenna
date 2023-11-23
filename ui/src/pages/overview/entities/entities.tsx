import { FetchInfo } from 'components/fetch-info/fetch-info'
import { useEntities } from 'data-services/hooks/entities/useEntities'
import { PaginationBar } from 'design-system/components/pagination-bar/pagination-bar'
import { Table } from 'design-system/components/table/table/table'
import { TableSortSettings } from 'design-system/components/table/types'
import { Error } from 'pages/error/error'
import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { usePagination } from 'utils/usePagination'
import { columns } from './entities-columns'
import styles from './styles.module.scss'

export const Entities = ({ collection }: { collection: string }) => {
  const { projectId } = useParams()
  const [sort, setSort] = useState<TableSortSettings>()
  const { pagination, setPage } = usePagination()
  const { entities, total, isLoading, isFetching, error } = useEntities(
    collection,
    {
      projectId,
      pagination,
      sort,
    }
  )

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
        items={entities}
        isLoading={isLoading}
        columns={columns(collection)}
        sortable
        sortSettings={sort}
        onSortSettingsChange={setSort}
      />
      {entities?.length ? (
        <PaginationBar
          pagination={pagination}
          total={total}
          setPage={setPage}
        />
      ) : null}
    </>
  )
}
