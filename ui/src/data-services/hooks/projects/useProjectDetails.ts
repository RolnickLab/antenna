import { useQuery } from '@tanstack/react-query'
import axios from 'axios'
import { API_URL } from 'data-services/constants'
import { Project, ServerProject } from 'data-services/models/project'
import { COLLECTION } from './constants'

const convertServerRecord = (record: ServerProject) => new Project(record)

export const useProjectDetails = (
  projectId: string
): {
  project?: Project
  isLoading: boolean
  isFetching: boolean
  error?: unknown
} => {
  const { data, isLoading, isFetching, error } = useQuery({
    queryKey: [COLLECTION, projectId],
    queryFn: () =>
      axios
        .get<Project>(`${API_URL}/${COLLECTION}/${projectId}`)
        .then((res) => convertServerRecord(res.data)),
  })

  return {
    project: data,
    isLoading,
    isFetching,
    error,
  }
}
