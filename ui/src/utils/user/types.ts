export type User = {
  loggedIn: boolean
  token?: string
}

export enum UserPermission {
  Update = 'update',
  Create = 'create',
  Delete = 'delete',
}

export interface UserContextValues {
  clearToken: () => void
  setToken: (token: string, from?: string) => void
  user: User
}
