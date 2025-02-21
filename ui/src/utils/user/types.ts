export type User = {
  loggedIn: boolean
  token?: string
}

export type UserInfo = {
  email?: string
  id: string
  image?: string
  name?: string
}

export enum UserPermission {
  Update = 'update',
  Create = 'create',
  Delete = 'delete',
  Populate = 'populate',
  Star = 'star',
}

export interface UserContextValues {
  clearToken: () => void
  setToken: (token: string, from?: string) => void
  user: User
}

export interface UserInfoContextValues {
  userInfo?: UserInfo
}
