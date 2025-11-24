import { useMembers } from 'data-services/hooks/team/useMembers'
import { ProjectDetails } from 'data-services/models/project-details'
import { PageHeader } from 'design-system/components/page-header/page-header'
import { PaginationBar } from 'design-system/components/pagination-bar/pagination-bar'
import { Table } from 'design-system/components/table/table/table'
import { PlusIcon } from 'lucide-react'
import { Button } from 'nova-ui-kit'
import { useEffect } from 'react'
import { useNavigate, useOutletContext } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { STRING, translate } from 'utils/language'
import { usePagination } from 'utils/usePagination'
import { useUserInfo } from 'utils/user/userInfoContext'
import { columns } from './team-columns'

export const Team = () => {
  const navigate = useNavigate()
  const { project } = useOutletContext<{
    project: ProjectDetails
  }>()
  const { pagination, setPage } = usePagination()
  const { members, total, isLoading, isFetching, error } = useMembers({
    projectId: project.id,
    pagination,
  })
  const { userInfo } = useUserInfo()

  useEffect(() => {
    if (!project.canUpdate) {
      navigate(APP_ROUTES.PROJECT_DETAILS({ projectId: project.id }))
    }
  }, [project.canUpdate])

  if (!project.canUpdate) {
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
        <Button size="small" variant="outline">
          <PlusIcon className="w-4 h-4" />
          <span>
            {translate(STRING.ENTITY_ADD, {
              type: translate(STRING.ENTITY_TYPE_MEMBER),
            })}
          </span>
        </Button>
      </PageHeader>
      <Table
        columns={columns(userInfo?.id)}
        error={error}
        isLoading={isLoading}
        items={members}
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
