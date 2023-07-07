import { FetchInfo } from 'components/fetch-info/fetch-info'
import { useJobDetails } from 'data-services/hooks/jobs/useJobDetails'
import { useJobs } from 'data-services/hooks/jobs/useJobs'
import * as Dialog from 'design-system/components/dialog/dialog'
import { Table } from 'design-system/components/table/table/table'
import { Error } from 'pages/error/error'
import { JobDetails } from 'pages/job-details/job-details'
import { useNavigate, useParams } from 'react-router-dom'
import { getRoute } from 'utils/getRoute'
import { STRING, translate } from 'utils/language'
import { columns } from './jobs-columns'
import styles from './jobs.module.scss'

export const Jobs = () => {
  const { id } = useParams()
  const { jobs, isLoading, isFetching, error } = useJobs()

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
      <Table items={jobs} isLoading={isLoading} columns={columns} />
      {!isLoading && id ? <JobDetailsDialog id={id} /> : null}
    </>
  )
}

const JobDetailsDialog = ({ id }: { id: string }) => {
  const navigate = useNavigate()
  const { job, isLoading } = useJobDetails(id)

  return (
    <Dialog.Root
      open={!!id}
      onOpenChange={() =>
        navigate(getRoute({ collection: 'jobs', keepSearchParams: true }))
      }
    >
      <Dialog.Content
        ariaCloselabel={translate(STRING.CLOSE)}
        isLoading={isLoading}
      >
        {job ? <JobDetails job={job} title="Job details" /> : null}
      </Dialog.Content>
    </Dialog.Root>
  )
}
