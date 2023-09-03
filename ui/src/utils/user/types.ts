export type User = {
  loggedIn: boolean
  token?: string
}

export interface UserContextValues {
  clearToken: () => void
  setToken: (token: string, from?: string) => void
  user: User
}
