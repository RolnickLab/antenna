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
  Create = 'create',
  Delete = 'delete',
  Populate = 'populate', // Custom collection permission
  Run = 'run', // Custom job permission
  RunSingleImage = 'run_single_image', // Custom job permission
  Star = 'star',
  Update = 'update',
}

export interface UserContextValues {
  clearToken: () => void
  setToken: (token: string, from?: string) => void
  user: User
}

export interface UserInfoContextValues {
  userInfo?: UserInfo
}
