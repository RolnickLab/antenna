import { FetchInfo } from 'components/fetch-info/fetch-info'
import { useJobs } from 'data-services/hooks/useJobs'
import { Table } from 'design-system/components/table/table/table'
import { Error } from 'pages/error/error'
import { JobDetailsDialog } from 'pages/job-details/job-details-dialog'
import { useNavigate, useParams } from 'react-router-dom'
import { columns } from './jobs-columns'
import styles from './jobs.module.scss'

export const Jobs = () => {
  const { id } = useParams()
  const navigate = useNavigate()
  const { jobs, isLoading, isFetching, error } = useJobs()

  if (!isLoading && error) {
    return <Error />
  }

  const job = jobs?.find((j) => j.id === id)
  const detailsOpen = !!job

  return (
    <>
      {isFetching && (
        <div className={styles.fetchInfoWrapper}>
          <FetchInfo isLoading={isLoading} />
        </div>
      )}
      <Table items={jobs} isLoading={isLoading} columns={columns} />
      <JobDetailsDialog
        job={job}
        open={detailsOpen}
        onOpenChange={() => navigate('/jobs')}
      />
    </>
  )
}
