import { usePipelines } from 'data-services/hooks/pipelines/usePipelines'
import { useProjectDetails } from 'data-services/hooks/projects/useProjectDetails'
import { PageHeader } from 'design-system/components/page-header/page-header'
import { PaginationBar } from 'design-system/components/pagination-bar/pagination-bar'
import { ColumnSettings } from 'design-system/components/table/column-settings/column-settings'
import { Table } from 'design-system/components/table/table/table'
import { TableSortSettings } from 'design-system/components/table/types'
import { PipelineDetailsDialog } from 'pages/pipeline-details/pipeline-details-dialog'
import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { STRING, translate } from 'utils/language'
import { useColumnSettings } from 'utils/useColumnSettings'
import { usePagination } from 'utils/usePagination'
import { columns } from './pipelines-columns'

export const Pipelines = () => {
  const { projectId, id } = useParams()
  const { columnSettings, setColumnSettings } = useColumnSettings('pipelines', {
    id: true,
    name: true,
    description: true,
    'created-at': true,
    'updated-at': true,
  })
  const [sort, setSort] = useState<TableSortSettings | undefined>({
    field: 'id',
    order: 'asc',
  })
  const { pagination, setPage } = usePagination()
  const { project } = useProjectDetails(projectId as string, true)
  const { pipelines, total, isLoading, isFetching, error } = usePipelines({
    projectId,
    pagination,
    sort,
  })

  return (
    <>
      <PageHeader
        title={translate(STRING.NAV_ITEM_PIPELINES)}
        subTitle={translate(STRING.RESULTS, {
          total,
        })}
        isLoading={isLoading}
        isFetching={isFetching}
        tooltip={translate(STRING.TOOLTIP_PIPELINE)}
      >
        <ColumnSettings
          columns={columns(projectId as string)}
          columnSettings={columnSettings}
          onColumnSettingsChange={setColumnSettings}
        />
      </PageHeader>
      <Table
        columns={columns(
          projectId as string,
          project?.settings.defaultProcessingPipeline?.id
        ).filter((column) => !!columnSettings[column.id])}
        error={error}
        isLoading={isLoading}
        items={pipelines}
        onSortSettingsChange={setSort}
        sortable
        sortSettings={sort}
      />
      {pipelines?.length ? (
        <PaginationBar
          compact
          pagination={pagination}
          setPage={setPage}
          total={total}
        />
      ) : null}
      {id ? <PipelineDetailsDialog id={id} /> : null}
    </>
  )
}
