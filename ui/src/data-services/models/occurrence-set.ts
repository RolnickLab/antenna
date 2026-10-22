import { UserPermission } from 'utils/user/types'

export interface ServerOccurrenceSet {
  id: number
  details: string
  name: string
  description: string
  occurrences_count: number
  created_at: string
  updated_at: string
  user_permissions: UserPermission[]
}
