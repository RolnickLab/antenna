import { API_ROUTES } from 'data-services/constants'
import { useCollections } from 'data-services/hooks/collections/useCollections'
import { PageHeader } from 'design-system/components/page-header/page-header'
import { PaginationBar } from 'design-system/components/pagination-bar/pagination-bar'
import { Table } from 'design-system/components/table/table/table'
import { TableSortSettings } from 'design-system/components/table/types'
import { Error } from 'pages/error/error'
import { NewEntityDialog } from 'pages/overview/entities/new-entity-dialog'
import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { STRING, translate } from 'utils/language'
import { usePagination } from 'utils/usePagination'
import { columns } from './collection-columns'

export const Collections = () => {
  const { projectId } = useParams()
  const [sort, setSort] = useState<TableSortSettings | undefined>({
    field: 'created_at',
    order: 'desc',
  })
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
      <PageHeader
        title={translate(STRING.TAB_ITEM_COLLECTIONS)}
        subTitle={translate(STRING.RESULTS, {
          total,
        })}
        isLoading={isLoading}
        isFetching={isFetching}
        tooltip={translate(STRING.TOOLTIP_COLLECTION)}
      >
        <NewEntityDialog
          collection={API_ROUTES.COLLECTIONS}
          type="collection"
        />
      </PageHeader>
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
