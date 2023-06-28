import { FetchInfo } from 'components/fetch-info/fetch-info'
import { useJobs } from 'data-services/hooks/useJobs'
import { Table } from 'design-system/components/table/table/table'
import { Error } from 'pages/error/error'
import { columns } from './jobs-columns'
import styles from './jobs.module.scss'

export const Jobs = () => {
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
    </>
  )
}
