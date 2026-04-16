import { useAlgorithms } from 'data-services/hooks/algorithm/useAlgorithms'
import { PageHeader } from 'design-system/components/page-header/page-header'
import { PaginationBar } from 'design-system/components/pagination-bar/pagination-bar'
import { ColumnSettings } from 'design-system/components/table/column-settings/column-settings'
import { Table } from 'design-system/components/table/table/table'
import { TableSortSettings } from 'design-system/components/table/types'
import { AlgorithmDetailsDialog } from 'pages/algorithm-details/algorithm-details-dialog'
import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { STRING, translate } from 'utils/language'
import { useColumnSettings } from 'utils/useColumnSettings'
import { usePagination } from 'utils/usePagination'
import { columns } from './algorithms-columns'

export const Algorithms = () => {
  const { projectId, id } = useParams()
  const { columnSettings, setColumnSettings } = useColumnSettings(
    'algorithms',
    {
      id: true,
      name: true,
      description: true,
      'task-type': true,
      'category-count': true,
    }
  )
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
  const tableColumns = columns({ projectId: projectId as string })

  return (
    <>
      <PageHeader
        title={translate(STRING.NAV_ITEM_ALGORITHMS)}
        subTitle={translate(STRING.RESULTS, {
          total,
        })}
        isLoading={isLoading}
        isFetching={isFetching}
        tooltip={translate(STRING.TOOLTIP_ALGORITHM)}
      >
        <ColumnSettings
          columns={tableColumns}
          columnSettings={columnSettings}
          onColumnSettingsChange={setColumnSettings}
        />
      </PageHeader>
      <Table
        columns={tableColumns.filter((column) => !!columnSettings[column.id])}
        error={error}
        isLoading={isLoading}
        items={algorithms}
        onSortSettingsChange={setSort}
        sortable
        sortSettings={sort}
      />
      {algorithms?.length ? (
        <PaginationBar
          compact
          pagination={pagination}
          setPage={setPage}
          total={total}
        />
      ) : null}
      {id ? <AlgorithmDetailsDialog id={id} /> : null}
    </>
  )
}
