import { useProjects } from 'data-services/hooks/projects/useProjects'
import { PageFooter } from 'design-system/components/page-footer/page-footer'
import { PageHeader } from 'design-system/components/page-header/page-header'
import { PaginationBar } from 'design-system/components/pagination-bar/pagination-bar'
import * as Tabs from 'design-system/components/tabs/tabs'
import { NewProjectDialog } from 'pages/project-details/new-project-dialog'
import { useState } from 'react'
import { STRING, translate } from 'utils/language'
import { usePagination } from 'utils/usePagination'
import { UserPermission } from 'utils/user/types'
import { useUser } from 'utils/user/userContext'
import { useUserInfo } from 'utils/user/userInfoContext'
import { ProjectGallery } from './project-gallery'

export const TABS = {
  MY_PROJECTS: 'my-projects',
  ALL_PROJECTS: 'all-projects',
}

export const Projects = () => {
  const { user } = useUser()
  const { userInfo } = useUserInfo()
  const [selectedTab, setSelectedTab] = useState(
    user.loggedIn ? TABS.MY_PROJECTS : TABS.ALL_PROJECTS
  )
  const { pagination, setPage } = usePagination()
  const filters =
    user.loggedIn && selectedTab === TABS.MY_PROJECTS
      ? [{ field: 'user_id', value: userInfo?.id }]
      : []
  const { projects, total, userPermissions, isLoading, isFetching, error } =
    useProjects({ pagination, filters })
  const canCreate = userPermissions?.includes(UserPermission.Create)

  return (
    <>
      <PageHeader
        title={translate(STRING.NAV_ITEM_PROJECTS)}
        subTitle={translate(STRING.RESULTS, { total: projects?.length ?? 0 })}
        isLoading={isLoading}
        isFetching={isFetching}
      >
        {user.loggedIn ? (
          <Tabs.Root onValueChange={setSelectedTab} value={selectedTab}>
            <Tabs.List>
              <Tabs.Trigger
                label={translate(STRING.TAB_ITEM_MY_PROJECTS)}
                value={TABS.MY_PROJECTS}
              />
              <Tabs.Trigger
                label={translate(STRING.TAB_ITEM_ALL_PROJECTS)}
                value={TABS.ALL_PROJECTS}
              />
            </Tabs.List>
          </Tabs.Root>
        ) : null}
        {canCreate ? <NewProjectDialog /> : null}
      </PageHeader>
      <ProjectGallery error={error} isLoading={isLoading} projects={projects} />
      <PageFooter>
        {projects?.length ? (
          <PaginationBar
            pagination={pagination}
            total={total}
            setPage={setPage}
          />
        ) : null}
      </PageFooter>
    </>
  )
}
