import { API_ROUTES } from 'data-services/constants'
import { useTaxaLists } from 'data-services/hooks/taxa-lists/useTaxaLists'
import { PageHeader } from 'design-system/components/page-header/page-header'
import { SortControl } from 'design-system/components/sort-control'
import { Table } from 'design-system/components/table/table/table'
import { DeploymentDetailsDialog } from 'pages/deployment-details/deployment-details-dialog'
import { NewEntityDialog } from 'pages/project/entities/new-entity-dialog'
import { useParams } from 'react-router-dom'
import { STRING, translate } from 'utils/language'
import { UserPermission } from 'utils/user/types'
import { useSort } from 'utils/useSort'
import { columns } from './taxa-list-columns'

export const TaxaLists = () => {
  const { projectId, id } = useParams()

  const { sort, setSort } = useSort({
    field: 'name',
    order: 'asc',
  })
  const { taxaLists, userPermissions, isLoading, isFetching, error } =
    useTaxaLists({
      projectId,
      pagination: { page: 0, perPage: 200 },
      sort,
    })
  const canCreate = userPermissions?.includes(UserPermission.Create)

  return (
    <>
      <PageHeader
        title={translate(STRING.NAV_ITEM_TAXA_LISTS)}
        subTitle={translate(STRING.RESULTS, {
          total: taxaLists?.length ?? 0,
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
            global
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
      {id ? <DeploymentDetailsDialog id={id} /> : null}
    </>
  )
}
