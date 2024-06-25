import { FetchInfo } from 'components/fetch-info/fetch-info'
import { usePipelines } from 'data-services/hooks/pipelines/usePipelines'
import { PaginationBar } from 'design-system/components/pagination-bar/pagination-bar'
import { Table } from 'design-system/components/table/table/table'
import { TableSortSettings } from 'design-system/components/table/types'
import { Error } from 'pages/error/error'
import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { usePagination } from 'utils/usePagination'
import { columns } from './pipelines-columns'
import styles from './pipelines.module.scss'

export const Pipelines = () => {
  const { projectId } = useParams()
  const [sort, setSort] = useState<TableSortSettings | undefined>({
    field: 'created_at',
    order: 'desc',
  })
  const { pagination, setPage } = usePagination()
  const { pipelines, total, isLoading, isFetching, error } = usePipelines({
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
        items={pipelines}
        isLoading={isLoading}
        columns={columns(projectId as string)}
        sortable
        sortSettings={sort}
        onSortSettingsChange={setSort}
      />
      {pipelines?.length ? (
        <PaginationBar
          pagination={pagination}
          total={total}
          setPage={setPage}
        />
      ) : null}
    </>
  )
}
