import { FetchInfo } from 'components/fetch-info/fetch-info'
import { useJobDetails } from 'data-services/hooks/jobs/useJobDetails'
import { useJobs } from 'data-services/hooks/jobs/useJobs'
import * as Dialog from 'design-system/components/dialog/dialog'
import { PaginationBar } from 'design-system/components/pagination/pagination-bar'
import { Table } from 'design-system/components/table/table/table'
import { Error } from 'pages/error/error'
import { JobDetails } from 'pages/job-details/job-details'
import { useNavigate, useParams } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { getAppRoute } from 'utils/getAppRoute'
import { STRING, translate } from 'utils/language'
import { usePagination } from 'utils/usePagination'
import { columns } from './jobs-columns'
import styles from './jobs.module.scss'

export const Jobs = () => {
  const { projectId, id } = useParams()
  const { pagination, setPrevPage, setNextPage } = usePagination()
  const { jobs, total, isLoading, isFetching, error } = useJobs({
    projectId,
    pagination,
  })

  if (!isLoading && error) {
    return <Error />
  }

  return (
    <>
      {isFetching && (
        <div className={styles.fetchInfoWrapper}>
          <FetchInfo isLoading={isLoading} />
        </div>
      )}
      <Table
        items={jobs}
        isLoading={isLoading}
        columns={columns(projectId as string)}
      />
      {!isLoading && id ? <JobDetailsDialog id={id} /> : null}
      {jobs?.length ? (
        <PaginationBar
          page={pagination.page}
          perPage={pagination.perPage}
          total={total}
          onPrevClick={setPrevPage}
          onNextClick={setNextPage}
        />
      ) : null}
    </>
  )
}

const JobDetailsDialog = ({ id }: { id: string }) => {
  const navigate = useNavigate()
  const { projectId } = useParams()
  const { job, isLoading, isFetching } = useJobDetails(id)

  return (
    <Dialog.Root
      open={!!id}
      onOpenChange={() =>
        navigate(
          getAppRoute({
            to: APP_ROUTES.JOBS({ projectId: projectId as string }),
            keepSearchParams: true,
          })
        )
      }
    >
      <Dialog.Content
        ariaCloselabel={translate(STRING.CLOSE)}
        isLoading={isLoading}
      >
        {job ? (
          <JobDetails job={job} title="Job details" isFetching={isFetching} />
        ) : null}
      </Dialog.Content>
    </Dialog.Root>
  )
}
