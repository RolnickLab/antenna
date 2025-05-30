import { ErrorState } from 'components/error-state/error-state'
import { API_ROUTES } from 'data-services/constants'
import { useProcessingServices } from 'data-services/hooks/processing-services/useProcessingServices'
import { PageHeader } from 'design-system/components/page-header/page-header'
import { PaginationBar } from 'design-system/components/pagination-bar/pagination-bar'
import { Table } from 'design-system/components/table/table/table'
import { TableSortSettings } from 'design-system/components/table/types'
import { ProcessingServiceDetailsDialog } from 'pages/processing-service-details/processing-service-details-dialog'
import { NewEntityDialog } from 'pages/project/entities/new-entity-dialog'
import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { STRING, translate } from 'utils/language'
import { usePagination } from 'utils/usePagination'
import { UserPermission } from 'utils/user/types'
import { columns } from './processing-services-columns'

export const ProcessingServices = () => {
  const { projectId, id } = useParams()
  const [sort, setSort] = useState<TableSortSettings | undefined>({
    field: 'id',
    order: 'asc',
  })
  const { pagination, setPage } = usePagination()
  const { items, userPermissions, total, isLoading, isFetching, error } =
    useProcessingServices({
      projectId,
      pagination,
      sort,
    })
  const canCreate = userPermissions?.includes(UserPermission.Create)

  if (!isLoading && error) {
    return <ErrorState error={error} />
  }

  return (
    <>
      <PageHeader
        title={translate(STRING.NAV_ITEM_PROCESSING_SERVICES)}
        subTitle={translate(STRING.RESULTS, {
          total,
        })}
        isLoading={isLoading}
        isFetching={isFetching}
        tooltip={translate(STRING.TOOLTIP_PROCESSING_SERVICE)}
      >
        {canCreate && (
          <NewEntityDialog
            collection={API_ROUTES.PROCESSING_SERVICES}
            type="service"
          />
        )}
      </PageHeader>
      <Table
        items={items}
        isLoading={isLoading}
        columns={columns(projectId as string, canCreate)}
        sortable
        sortSettings={sort}
        onSortSettingsChange={setSort}
      />
      {items?.length ? (
        <PaginationBar
          compact
          pagination={pagination}
          total={total}
          setPage={setPage}
        />
      ) : null}
      {id ? <ProcessingServiceDetailsDialog id={id} /> : null}
    </>
  )
}
