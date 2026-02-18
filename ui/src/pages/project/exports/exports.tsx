import { EmptyState } from 'components/empty-state/empty-state'
import { API_ROUTES } from 'data-services/constants'
import { useExports } from 'data-services/hooks/exports/useExports'
import { PageHeader } from 'design-system/components/page-header/page-header'
import { PaginationBar } from 'design-system/components/pagination-bar/pagination-bar'
import { Table } from 'design-system/components/table/table/table'
import { TableSortSettings } from 'design-system/components/table/types'
import { ExportDetailsDialog } from 'pages/export-details/export-details-dialog'
import { NewEntityDialog } from 'pages/project/entities/new-entity-dialog'
import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { DOCS_LINKS } from 'utils/constants'
import { STRING, translate } from 'utils/language'
import { usePagination } from 'utils/usePagination'
import { UserPermission } from 'utils/user/types'
import { columns } from './exports-columns'

export const Exports = () => {
  const { projectId, id } = useParams()
  const [sort, setSort] = useState<TableSortSettings | undefined>({
    field: 'created_at',
    order: 'desc',
  })
  const { pagination, setPage } = usePagination()
  const [poll, setPoll] = useState(false)
  const { exports, userPermissions, total, isLoading, isFetching, error } =
    useExports(
      {
        projectId,
        pagination,
        sort,
      },
      poll
    )
  const canCreate = userPermissions?.includes(UserPermission.Create)

  useEffect(() => {
    // If any export is in progress, we want to poll the endpoint so we can show updates
    if (exports?.some(({ job }) => job?.progress.value !== 1)) {
      setPoll(true)
    } else {
      setPoll(false)
    }
  }, [exports])

  return (
    <>
      <PageHeader
        docsLink={DOCS_LINKS.EXPORTING_DATA}
        isFetching={isFetching}
        isLoading={isLoading}
        subTitle={translate(STRING.RESULTS, { total })}
        title={translate(STRING.NAV_ITEM_EXPORTS)}
      >
        {canCreate && (
          <NewEntityDialog
            collection={API_ROUTES.EXPORTS}
            type="export"
            isCompact
          />
        )}
      </PageHeader>
      {exports && exports.length === 0 && canCreate ? (
        <EmptyState>
          <NewEntityDialog
            buttonSize="default"
            buttonVariant="success"
            collection={API_ROUTES.EXPORTS}
            isCompact
            type="export"
          />
        </EmptyState>
      ) : (
        <Table
          columns={columns(projectId as string)}
          error={error}
          isLoading={isLoading}
          items={exports}
          onSortSettingsChange={setSort}
          sortable
          sortSettings={sort}
        />
      )}
      {exports?.length ? (
        <PaginationBar
          compact
          pagination={pagination}
          setPage={setPage}
          total={total}
        />
      ) : null}
      {id ? <ExportDetailsDialog id={id} /> : null}
    </>
  )
}
