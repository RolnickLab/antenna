import { Role } from './role'

export type ServerMember = any // TODO: Update this type

export type Member = {
  canDelete: boolean
  canUpdate: boolean
  email: string
  id: string
  image?: string
  name: string
  role: Role
  userId: string
}
