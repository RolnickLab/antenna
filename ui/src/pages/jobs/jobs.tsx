import { FilterControl } from 'components/filtering/filter-control'
import { FilterSection } from 'components/filtering/filter-section'
import { useJobDetails } from 'data-services/hooks/jobs/useJobDetails'
import { useJobs } from 'data-services/hooks/jobs/useJobs'
import * as Dialog from 'design-system/components/dialog/dialog'
import { PageFooter } from 'design-system/components/page-footer/page-footer'
import { PageHeader } from 'design-system/components/page-header/page-header'
import { PaginationBar } from 'design-system/components/pagination-bar/pagination-bar'
import { SortControl } from 'design-system/components/sort-control'
import { ColumnSettings } from 'design-system/components/table/column-settings/column-settings'
import { Table } from 'design-system/components/table/table/table'
import _ from 'lodash'
import { JobDetails } from 'pages/job-details/job-details'
import { NewJobDialog } from 'pages/job-details/new-job-dialog'
import { useContext, useEffect } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { BreadcrumbContext } from 'utils/breadcrumbContext'
import { APP_ROUTES, DOCS_LINKS } from 'utils/constants'
import { getAppRoute } from 'utils/getAppRoute'
import { STRING, translate } from 'utils/language'
import { useColumnSettings } from 'utils/useColumnSettings'
import { useFilters } from 'utils/useFilters'
import { usePagination } from 'utils/usePagination'
import { useSort } from 'utils/useSort'
import { UserPermission } from 'utils/user/types'
import { columns } from './jobs-columns'

export const Jobs = () => {
  const { projectId, id } = useParams()
  const { pagination, setPage } = usePagination()
  const { filters } = useFilters()
  const { sort, setSort } = useSort({ field: 'created_at', order: 'desc' })
  const { columnSettings, setColumnSettings } = useColumnSettings('jobs', {
    name: true,
    status: true,
    'job-type': true,
    pipeline: true,
    'created-at': true,
  })
  const { jobs, userPermissions, total, isLoading, isFetching, error } =
    useJobs({
      projectId,
      sort,
      pagination,
      filters,
    })
  const canCreate = userPermissions?.includes(UserPermission.Create)

  return (
    <div className="flex flex-col gap-6 md:flex-row">
      <div className="space-y-6">
        <FilterSection defaultOpen>
          <FilterControl field="source_image_single" readonly />
          <FilterControl field="status" />
          <FilterControl field="job_type_key" />
          <FilterControl field="deployment" />
          <FilterControl field="pipeline" />
          <FilterControl field="source_image_collection" />
        </FilterSection>
      </div>
      <div className="w-full overflow-hidden">
        <PageHeader
          docsLink={DOCS_LINKS.PROCESSING_DATA}
          isFetching={isFetching}
          isLoading={isLoading}
          subTitle={translate(STRING.RESULTS, { total })}
          title={translate(STRING.NAV_ITEM_JOBS)}
          tooltip={translate(STRING.TOOLTIP_JOB)}
        >
          <SortControl
            columns={columns(projectId as string)}
            setSort={setSort}
            sort={sort}
          />
          {canCreate ? <NewJobDialog /> : null}
          <ColumnSettings
            columns={columns(projectId as string)}
            columnSettings={columnSettings}
            onColumnSettingsChange={setColumnSettings}
          />
        </PageHeader>
        <Table
          columns={columns(projectId as string).filter(
            (column) => column.id === 'actions' || !!columnSettings[column.id]
          )}
          error={error}
          items={jobs}
          isLoading={!id && isLoading}
          sortable
          sortSettings={sort}
          onSortSettingsChange={setSort}
        />
      </div>
      <PageFooter>
        {jobs?.length ? (
          <PaginationBar
            pagination={pagination}
            total={total}
            setPage={setPage}
          />
        ) : null}
      </PageFooter>
      {id ? <JobDetailsDialog id={id} /> : null}
    </div>
  )
}

const JobDetailsDialog = ({ id }: { id: string }) => {
  const navigate = useNavigate()
  const { projectId } = useParams()
  const { setDetailBreadcrumb } = useContext(BreadcrumbContext)
  const { job, isLoading, isFetching, error } = useJobDetails(id)

  useEffect(() => {
    setDetailBreadcrumb(job ? { title: job.name } : undefined)

    return () => {
      setDetailBreadcrumb(undefined)
    }
  }, [job])

  const closeDialog = () =>
    navigate(
      getAppRoute({
        to: APP_ROUTES.JOBS({ projectId: projectId as string }),
        keepSearchParams: true,
      })
    )

  return (
    <Dialog.Root open={!!id} onOpenChange={closeDialog}>
      <Dialog.Content
        ariaCloselabel={translate(STRING.CLOSE)}
        isLoading={isLoading}
        error={error}
      >
        {job ? (
          <JobDetails
            job={job}
            title={translate(STRING.ENTITY_DETAILS, {
              type: _.capitalize(translate(STRING.ENTITY_TYPE_JOB)),
            })}
            isFetching={isFetching}
            onDelete={closeDialog}
          />
        ) : null}
      </Dialog.Content>
    </Dialog.Root>
  )
}
