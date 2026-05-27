import { useProjects } from 'data-services/hooks/projects/useProjects'
import {
  Button,
  PageFooter,
  PageHeader,
  PaginationBar,
  SortControl,
  Tabs,
} from 'nova-ui-kit'
import { NewProjectDialog } from 'pages/project-details/new-project-dialog'
import { DOCS_LINKS } from 'utils/constants'
import { STRING, translate } from 'utils/language'
import { usePagination } from 'utils/usePagination'
import { UserPermission } from 'utils/user/types'
import { useUser } from 'utils/user/userContext'
import { useUserInfo } from 'utils/user/userInfoContext'
import { useSelectedView } from 'utils/useSelectedView'
import { useSort } from 'utils/useSort'
import { ProjectGallery } from './project-gallery'

export const TABS = {
  MY_PROJECTS: 'my-projects',
  ALL_PROJECTS: 'all-projects',
}

const SORT_FIELDS = [
  { id: 'name', name: translate(STRING.FIELD_LABEL_NAME) },
  { id: 'created_at', name: translate(STRING.FIELD_LABEL_CREATED_AT) },
  { id: 'updated_at', name: translate(STRING.FIELD_LABEL_UPDATED_AT) },
  {
    id: 'last_capture_timestamp',
    name: translate(STRING.SORT_RECENT_CAPTURES),
    defaultSortOrder: 'desc' as const,
  },
  {
    id: 'last_occurrence_updated_at',
    name: translate(STRING.SORT_OCCURRENCE_UPDATES),
    defaultSortOrder: 'desc' as const,
  },
  {
    id: 'last_job_updated_at',
    name: translate(STRING.SORT_JOBS_ACTIVITY),
    defaultSortOrder: 'desc' as const,
  },
]

export const Projects = () => {
  const { user } = useUser()
  const { userInfo } = useUserInfo()
  const { selectedView: selectedTab, setSelectedView: setSelectedTab } =
    useSelectedView(user.loggedIn ? TABS.MY_PROJECTS : TABS.ALL_PROJECTS)
  const { sort, setSort } = useSort()
  const { pagination, setPage } = usePagination({ perPage: 40 })
  const filters =
    user.loggedIn && selectedTab === TABS.MY_PROJECTS
      ? [{ field: 'user_id', value: userInfo?.id }]
      : []
  const { projects, total, userPermissions, isLoading, isFetching, error } =
    useProjects({ pagination, filters, sort })
  const canCreate = userPermissions?.includes(UserPermission.Create)

  return (
    <>
      <PageHeader
        docsLink={DOCS_LINKS.PROJECT_CREATION}
        isFetching={isFetching}
        isLoading={isLoading}
        subTitle={translate(STRING.RESULTS, { total: total ?? 0 })}
        title={translate(STRING.NAV_ITEM_PROJECTS)}
      >
        {user.loggedIn ? (
          <Tabs.Root
            onValueChange={(value) => {
              setSelectedTab(value)
              setPage(0)
            }}
            value={selectedTab}
          >
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
        <SortControl
          columns={SORT_FIELDS.map((field) => ({
            ...field,
            sortField: field.id,
          }))}
          setSort={setSort}
          sort={sort}
        />
      </PageHeader>
      {projects && projects.length === 0 && canCreate ? (
        <div className="flex flex-col items-center pt-32">
          <h1 className="mb-8 heading-large">Get started</h1>
          <p className="text-center body-large mb-16">
            To start use Antenna, create your first project or view the public
            ones.
          </p>
          <div className="flex flex-col items-center gap-8">
            <NewProjectDialog buttonSize="default" buttonVariant="success" />
            <p className="body-base">or</p>
            <Button
              variant="outline"
              onClick={() => setSelectedTab(TABS.ALL_PROJECTS)}
            >
              <span>View public projects</span>
            </Button>
          </div>
        </div>
      ) : (
        <ProjectGallery
          error={error}
          isLoading={isLoading}
          projects={projects}
        />
      )}
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
