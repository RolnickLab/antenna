import { SearchInput } from 'components/search-input/search-input'
import { useProjects } from 'data-services/hooks/projects/useProjects'
import { Grid2X2Icon, TableIcon } from 'lucide-react'
import {
  Button,
  ColumnSettings,
  PageFooter,
  PageHeader,
  PaginationBar,
  Table,
  Tabs,
  ToggleGroup,
} from 'nova-ui-kit'
import { NewProjectDialog } from 'pages/project-details/new-project-dialog'
import { DOCS_LINKS } from 'utils/constants'
import { STRING, translate } from 'utils/language'
import { usePagination } from 'utils/usePagination'
import { useSearch } from 'utils/useSearch'
import { useColumnSettings } from 'utils/useColumnSettings'
import { UserPermission } from 'utils/user/types'
import { useUser } from 'utils/user/userContext'
import { useUserInfo } from 'utils/user/userInfoContext'
import { useSelectedView } from 'utils/useSelectedView'
import { useSort } from 'utils/useSort'
import { columns } from './project-columns'
import { ProjectGallery } from './project-gallery'

export const TABS = {
  MY_PROJECTS: 'my-projects',
  ALL_PROJECTS: 'all-projects',
}

export const Projects = () => {
  const { user } = useUser()
  const { userInfo } = useUserInfo()
  const { selectedView: selectedTab, setSelectedView: setSelectedTab } =
    useSelectedView(user.loggedIn ? TABS.MY_PROJECTS : TABS.ALL_PROJECTS)
  const { selectedView: layout, setSelectedView: setLayout } = useSelectedView(
    'gallery',
    'layout'
  )
  const { columnSettings, setColumnSettings } = useColumnSettings('projects', {
    image: true,
    name: true,
    deployments: true,
    captures: true,
    occurrences: true,
    taxa: true,
    members: false,
    'last-capture': true,
    'last-occurrence-update': false,
    'last-job-update': false,
    'created-at': false,
    'updated-at': false,
  })
  const { sort, setSort } = useSort()
  const { pagination, setPage } = usePagination({ perPage: 40 })
  const { search, setSearch } = useSearch()
  const filters = [
    ...(user.loggedIn && selectedTab === TABS.MY_PROJECTS
      ? [{ field: 'user_id', value: userInfo?.id }]
      : []),
    ...(search ? [{ field: 'search', value: search }] : []),
    // Totals and activity dates are only shown, and only computed, in the table.
    ...(layout === 'table' ? [{ field: 'with_counts', value: 'true' }] : []),
  ]
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
        <SearchInput
          label={translate(STRING.SEARCH_PROJECTS)}
          value={search}
          onChange={setSearch}
        />
        <ToggleGroup
          items={[
            {
              value: 'table',
              label: translate(STRING.TAB_ITEM_TABLE),
              Icon: TableIcon,
            },
            {
              value: 'gallery',
              label: translate(STRING.TAB_ITEM_GALLERY),
              Icon: Grid2X2Icon,
            },
          ]}
          value={layout}
          onValueChange={setLayout}
        />
        {canCreate ? <NewProjectDialog /> : null}
        {layout === 'table' ? (
          <ColumnSettings
            columns={columns}
            columnSettings={columnSettings}
            onColumnSettingsChange={setColumnSettings}
          />
        ) : null}
      </PageHeader>
      {projects && projects.length === 0 && canCreate && !search ? (
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
      ) : layout === 'table' ? (
        <Table
          columns={columns.filter((column) => !!columnSettings[column.id])}
          error={error}
          isLoading={isLoading}
          items={projects}
          onSortSettingsChange={setSort}
          sortable
          sortSettings={sort}
        />
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
