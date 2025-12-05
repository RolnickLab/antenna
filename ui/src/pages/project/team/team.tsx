import { useMembers } from 'data-services/hooks/team/useMembers'
import { ProjectDetails } from 'data-services/models/project-details'
import { PageHeader } from 'design-system/components/page-header/page-header'
import { PaginationBar } from 'design-system/components/pagination-bar/pagination-bar'
import { Table } from 'design-system/components/table/table/table'
import { useEffect } from 'react'
import { useNavigate, useOutletContext } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { STRING, translate } from 'utils/language'
import { usePagination } from 'utils/usePagination'
import { UserPermission } from 'utils/user/types'
import { useUserInfo } from 'utils/user/userInfoContext'
import { useSort } from 'utils/useSort'
import { AboutRoles } from './about-roles'
import { AddMemberDialog } from './add-member-dialog'
import { columns } from './team-columns'

export const Team = () => {
  const navigate = useNavigate()
  const { project } = useOutletContext<{
    project: ProjectDetails
  }>()
  const { pagination, setPage } = usePagination()
  const { sort, setSort } = useSort()
  const { members, userPermissions, total, isLoading, isFetching, error } =
    useMembers(project.id, {
      pagination,
    })
  const { userInfo } = useUserInfo()
  const canCreate = userPermissions?.includes(UserPermission.Create)

  useEffect(() => {
    if (!project.isMember) {
      navigate(APP_ROUTES.PROJECT_DETAILS({ projectId: project.id }))
    }
  }, [project.isMember])

  if (!project.isMember) {
    return null
  }

  return (
    <>
      <PageHeader
        title={translate(STRING.NAV_ITEM_TEAM)}
        subTitle={translate(STRING.RESULTS_MEMBERS, {
          total,
        })}
        isLoading={isLoading}
        isFetching={isFetching}
      >
        <AboutRoles />
        {canCreate ? <AddMemberDialog /> : null}
      </PageHeader>
      <Table
        columns={columns(userInfo?.id)}
        error={error}
        isLoading={isLoading}
        items={members}
        onSortSettingsChange={setSort}
        sortable
        sortSettings={sort}
      />
      {members?.length ? (
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
