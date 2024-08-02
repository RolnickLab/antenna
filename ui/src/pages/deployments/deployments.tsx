import { useDeployments } from 'data-services/hooks/deployments/useDeployments'
import { PageHeader } from 'design-system/components/page-header/page-header'
import { Table } from 'design-system/components/table/table/table'
import { DeploymentDetailsDialog } from 'pages/deployment-details/deployment-details-dialog'
import { NewDeploymentDialog } from 'pages/deployment-details/new-deployment-dialog'
import { Error } from 'pages/error/error'
import { useParams } from 'react-router-dom'
import { STRING, translate } from 'utils/language'
import { useClientSideSort } from 'utils/useClientSideSort'
import { UserPermission } from 'utils/user/types'
import { columns } from './deployment-columns'

export const Deployments = () => {
  const { projectId, id } = useParams()
  const { deployments, userPermissions, isLoading, isFetching, error } =
    useDeployments({
      projectId,
      pagination: { page: 0, perPage: 200 },
    })
  const { sortedItems, sort, setSort } = useClientSideSort({
    items: deployments,
    defaultSort: { field: 'name', order: 'asc' },
  })
  const canCreate = userPermissions?.includes(UserPermission.Create)

  if (!isLoading && error) {
    return <Error />
  }

  return (
    <>
      <PageHeader
        title={translate(STRING.NAV_ITEM_DEPLOYMENTS)}
        subTitle={translate(STRING.RESULTS, {
          total: deployments?.length ?? 0,
        })}
        isLoading={isLoading}
        isFetching={isFetching}
        tooltip={translate(STRING.TOOLTIP_DEPLOYMENT)}
      >
        {canCreate ? <NewDeploymentDialog /> : null}
      </PageHeader>
      <Table
        items={sortedItems}
        isLoading={isLoading}
        columns={columns(projectId as string)}
        sortable
        sortSettings={sort}
        onSortSettingsChange={setSort}
      />
      {!isLoading && id ? <DeploymentDetailsDialog id={id} /> : null}
    </>
  )
}
