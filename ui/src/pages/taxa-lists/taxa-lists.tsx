import { API_ROUTES } from 'data-services/constants'
import { useTaxaLists } from 'data-services/hooks/taxa-lists/useTaxaLists'
import { PageHeader, PaginationBar, SortControl, Table } from 'nova-ui-kit'
import { NewEntityDialog } from 'pages/project/entities/new-entity-dialog'
import { useParams } from 'react-router-dom'
import { STRING, translate } from 'utils/language'
import { usePagination } from 'utils/usePagination'
import { UserPermission } from 'utils/user/types'
import { useSort } from 'utils/useSort'
import { columns } from './taxa-list-columns'

export const TaxaLists = () => {
  const { projectId, id } = useParams()
  const { sort, setSort } = useSort({
    field: 'name',
    order: 'asc',
  })
  const { pagination, setPage } = usePagination()
  const { taxaLists, total, userPermissions, isLoading, isFetching, error } =
    useTaxaLists({
      projectId,
      pagination,
      sort,
    })
  const canCreate = userPermissions?.includes(UserPermission.Create)
  const tableColumns = columns({ projectId: projectId as string })

  return (
    <>
      <PageHeader
        title={translate(STRING.NAV_ITEM_TAXA_LISTS)}
        subTitle={translate(STRING.RESULTS, { total })}
        isLoading={isLoading}
        isFetching={isFetching}
      >
        {canCreate && (
          <NewEntityDialog
            collection={API_ROUTES.TAXA_LISTS}
            isCompact
            type={translate(STRING.ENTITY_TYPE_TAXA_LIST)}
          />
        )}
        <SortControl columns={tableColumns} setSort={setSort} sort={sort} />
      </PageHeader>
      <Table
        columns={tableColumns}
        error={error}
        isLoading={!id && isLoading}
        items={taxaLists}
        onSortSettingsChange={setSort}
        sortable
        sortSettings={sort}
      />
      {taxaLists?.length ? (
        <PaginationBar
          compact
          pagination={pagination}
          setPage={setPage}
          total={total}
        />
      ) : null}
    </>
  )
}
