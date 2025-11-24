import { Role } from './role'

export type Member = {
  email: string
  id: string
  image?: string
  name: string
  role: Role
}
