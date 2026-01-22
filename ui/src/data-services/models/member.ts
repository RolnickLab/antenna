import { Role } from './role'
import { UserPermission } from 'utils/user/types'

export type ServerMember = {
  created_at: string
  id: string
  role: Role
  updated_at: string
  user: {
    id: string
    name: string
    email: string
    image?: string
  }
  user_permissions: UserPermission[]
}

export type Member = {
  addedAt: Date
  canDelete: boolean
  canUpdate: boolean
  email: string
  id: string
  image?: string
  name: string
  role: Role
  updatedAt?: Date
  userId: string
}
