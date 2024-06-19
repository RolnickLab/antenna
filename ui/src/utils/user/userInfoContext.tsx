import { useUserInfo as _useUserInfo } from 'data-services/hooks/auth/useUserInfo'
import { ReactNode, createContext, useContext } from 'react'
import { UserInfoContextValues } from './types'

export const UserInfoContext = createContext<UserInfoContextValues>({})

export const UserInfoContextProvider = ({
  children,
}: {
  children: ReactNode
}) => {
  const { userInfo } = _useUserInfo()

  return (
    <UserInfoContext.Provider
      value={{
        userInfo,
      }}
    >
      {children}
    </UserInfoContext.Provider>
  )
}

export const useUserInfo = () => useContext(UserInfoContext)
