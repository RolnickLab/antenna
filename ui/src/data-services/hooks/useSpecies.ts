import { FetchParams } from 'data-services/types'
import { ServerEvent, Species } from '../models/species'
import { useGetList } from './useGetList'

const convertServerRecord = (record: ServerEvent) => new Species(record)

export const useSpecies = (
  params?: FetchParams
): {
  species: Species[]
  total: number
  isLoading: boolean
  error?: string
} => {
  const {
    data: species,
    isLoading,
    error,
  } = useGetList<ServerEvent, Species>(
    { collection: 'species', params },
    convertServerRecord
  )

  return {
    species,
    total: species.length, // TODO: Until we get total in response
    isLoading,
    error,
  }
}
