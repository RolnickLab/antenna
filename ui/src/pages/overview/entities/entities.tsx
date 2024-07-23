import { useEntities } from 'data-services/hooks/entities/useEntities'
import { PageHeader } from 'design-system/components/page-header/page-header'
import { PaginationBar } from 'design-system/components/pagination-bar/pagination-bar'
import { Table } from 'design-system/components/table/table/table'
import { TableSortSettings } from 'design-system/components/table/types'
import { Error } from 'pages/error/error'
import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { STRING, translate } from 'utils/language'
import { usePagination } from 'utils/usePagination'
import { columns } from './entities-columns'
import { NewEntityDialog } from './new-entity-dialog'

export const Entities = ({
  title,
  collection,
  type,
  tooltip,
}: {
  title: string
  collection: string
  type: string
  tooltip?: string
}) => {
  const { projectId } = useParams()
  const [sort, setSort] = useState<TableSortSettings | undefined>({
    field: 'created_at',
    order: 'desc',
  })
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
      <PageHeader
        title={title}
        subTitle={translate(STRING.RESULTS, {
          total,
        })}
        isLoading={isLoading}
        isFetching={isFetching}
        tooltip={tooltip}
      >
        <NewEntityDialog collection={collection} type={type} />
      </PageHeader>
      <Table
        items={entities}
        isLoading={isLoading}
        columns={columns(collection, type)}
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
