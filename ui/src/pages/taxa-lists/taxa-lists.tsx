import { API_ROUTES } from 'data-services/constants'
import { useTaxaLists } from 'data-services/hooks/taxa-lists/useTaxaLists'
import { PageHeader } from 'design-system/components/page-header/page-header'
import { PaginationBar } from 'design-system/components/pagination-bar/pagination-bar'
import { SortControl } from 'design-system/components/sort-control'
import { Table } from 'design-system/components/table/table/table'
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

  return (
    <>
      <PageHeader
        title={translate(STRING.NAV_ITEM_TAXA_LISTS)}
        subTitle={translate(STRING.RESULTS, {
          total: total ?? taxaLists?.length ?? 0,
        })}
        isLoading={isLoading}
        isFetching={isFetching}
      >
        <SortControl
          columns={columns(projectId as string)}
          setSort={setSort}
          sort={sort}
        />
        {canCreate && (
          <NewEntityDialog
            collection={API_ROUTES.TAXA_LISTS}
            isCompact
            type={translate(STRING.ENTITY_TYPE_TAXA_LIST)}
          />
        )}
      </PageHeader>
      <Table
        columns={columns(projectId as string)}
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
