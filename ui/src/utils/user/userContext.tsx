/* eslint-disable @typescript-eslint/no-empty-function */

import { useQueryClient } from '@tanstack/react-query'
import { ReactNode, createContext, useContext, useState } from 'react'
import { AUTH_TOKEN_STORAGE_KEY } from './constants'
import { User, UserContextValues } from './types'

export const UserContext = createContext<UserContextValues>({
  clearToken: () => {},
  setToken: () => {},
  user: {
    loggedIn: false,
  },
})

export const UserContextProvider = ({ children }: { children: ReactNode }) => {
  const queryClient = useQueryClient()

  const [user, setUser] = useState<User>({
    loggedIn: !!localStorage.getItem(AUTH_TOKEN_STORAGE_KEY),
    token: localStorage.getItem(AUTH_TOKEN_STORAGE_KEY) ?? undefined,
  })

  const setToken = (token: string) => {
    localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, token)
    setUser({ loggedIn: true, token })
    queryClient.removeQueries()
  }

  const clearToken = () => {
    localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY)
    setUser({ loggedIn: false })
    queryClient.removeQueries()
  }

  return (
    <UserContext.Provider
      value={{
        clearToken,
        setToken,
        user,
      }}
    >
      {children}
    </UserContext.Provider>
  )
}

export const useUser = () => useContext(UserContext)
