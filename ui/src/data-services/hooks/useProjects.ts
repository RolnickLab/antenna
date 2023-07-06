import { useQuery } from '@tanstack/react-query'
import axios from 'axios'
import { API_URL } from 'data-services/constants'
import { Project, ServerProject } from 'data-services/models/project'

const COLLECTION = 'projects'
const ID = '1'

const convertServerRecord = (record: ServerProject) => new Project(record)

export const useProject = (): {
  project?: Project
  isLoading: boolean
  isFetching: boolean
  error?: unknown
} => {
  const { data, isLoading, isFetching, error } = useQuery({
    queryKey: [COLLECTION, ID],
    queryFn: () =>
      axios
        .get<Project>(`${API_URL}/${COLLECTION}/${ID}`)
        .then((res) => convertServerRecord(res.data)),
  })

  return {
    project: data,
    isLoading,
    isFetching,
    error,
  }
}
