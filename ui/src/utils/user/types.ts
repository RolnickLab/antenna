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
  Cancel = 'cancel', // Custom job permission
  Create = 'create',
  Delete = 'delete',
  Populate = 'populate', // Custom collection permission
  Retry = 'retry', // Custom job permission
  Run = 'run', // Custom job permission
  Star = 'star',
  Update = 'update', // Custom capture permission
}

export interface UserContextValues {
  clearToken: () => void
  setToken: (token: string, from?: string) => void
  user: User
}

export interface UserInfoContextValues {
  userInfo?: UserInfo
}
