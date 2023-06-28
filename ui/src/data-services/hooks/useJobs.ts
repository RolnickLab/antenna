import { Job, ServerJob } from 'data-services/models/job'
import data from '../example-data/jobs.json'

const convertServerRecord = (record: ServerJob) => new Job(record)

export const useJobs = (): {
  jobs?: Job[]
  isLoading: boolean
  isFetching: boolean
  error?: unknown
} => {
  const jobs = data.map(convertServerRecord)

  return { jobs, isLoading: false, isFetching: false, error: undefined }
}
