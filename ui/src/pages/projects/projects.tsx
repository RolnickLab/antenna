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
import { ProjectGallery } from './project-gallery'

export const TABS = {
  USER_PROJECTS: 'user-projects',
  ALL_PROJECTS: 'all-projects',
}

export const Projects = () => {
  const { user } = useUser()
  const [selectedTab, setSelectedTab] = useState(
    user.loggedIn ? TABS.USER_PROJECTS : TABS.ALL_PROJECTS
  )
  const { pagination, setPage } = usePagination()
  const filters =
    user.loggedIn && selectedTab === TABS.USER_PROJECTS
      ? [{ field: 'public', value: 'false' }]
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
                label={translate(STRING.TAB_ITEM_USER_PROJECTS)}
                value={TABS.USER_PROJECTS}
              />
              <Tabs.Trigger
                label={translate(STRING.TAB_ITEM_ALL_PROJECTS)}
                value={TABS.ALL_PROJECTS}
              />
            </Tabs.List>
          </Tabs.Root>
        ) : null}
      </PageHeader>
      <ProjectGallery error={error} isLoading={isLoading} projects={projects} />
      {canCreate && selectedTab === TABS.USER_PROJECTS ? (
        <div className="pt-4">
          <NewProjectDialog />
        </div>
      ) : null}
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
