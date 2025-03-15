import { useAlgorithms } from 'data-services/hooks/algorithm/useAlgorithms'
import { PageHeader } from 'design-system/components/page-header/page-header'
import { PaginationBar } from 'design-system/components/pagination-bar/pagination-bar'
import { Table } from 'design-system/components/table/table/table'
import { TableSortSettings } from 'design-system/components/table/types'
import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { STRING, translate } from 'utils/language'
import { usePagination } from 'utils/usePagination'
import { columns } from './algorithms-columns'

export const Algorithms = () => {
  const { projectId } = useParams()
  const [sort, setSort] = useState<TableSortSettings | undefined>({
    field: 'id',
    order: 'asc',
  })
  const { pagination, setPage } = usePagination()
  const { algorithms, total, isLoading, isFetching, error } = useAlgorithms({
    projectId,
    pagination,
    sort,
  })

  return (
    <>
      <PageHeader
        title={translate(STRING.TAB_ITEM_ALGORITHMS)}
        subTitle={translate(STRING.RESULTS, {
          total,
        })}
        isLoading={isLoading}
        isFetching={isFetching}
        tooltip={translate(STRING.TOOLTIP_ALGORITHM)}
      />
      <Table
        columns={columns(projectId as string)}
        error={error}
        isLoading={isLoading}
        items={algorithms}
        onSortSettingsChange={setSort}
        sortable
        sortSettings={sort}
      />
      {algorithms?.length ? (
        <PaginationBar
          pagination={pagination}
          total={total}
          setPage={setPage}
        />
      ) : null}
    </>
  )
}
