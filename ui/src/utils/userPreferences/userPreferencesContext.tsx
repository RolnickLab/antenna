import { createContext, ReactNode, useContext, useState } from 'react'
import { useCookieContext } from '../cookies/cookieContext'
import { DEFAULT_PREFERENCES, USER_PREFERENCES_STORAGE_KEY } from './constants'
import { UserPreferences, UserPreferencesContextValues } from './types'

export const UserPreferencesContext =
  createContext<UserPreferencesContextValues>({
    userPreferences: DEFAULT_PREFERENCES,
    setUserPreferences: () => {},
  })

export const UserPreferencesContextProvider = ({
  children,
}: {
  children: ReactNode
}) => {
  const { accepted, settings } = useCookieContext()
  const hasStorageConsent = accepted && settings.functionality // Do not store preferences is browser unless user has given consent

  const [userPreferences, setUserPreferences] = useState<UserPreferences>(
    () => {
      // TODO: For logged in users, here we could check backend for stored preferences
      const storedPreferences =
        hasStorageConsent && localStorage.getItem(USER_PREFERENCES_STORAGE_KEY)
      if (!storedPreferences) {
        return DEFAULT_PREFERENCES
      }
      try {
        return JSON.parse(storedPreferences) as UserPreferences
      } catch {
        return DEFAULT_PREFERENCES
      }
    }
  )

  return (
    <UserPreferencesContext.Provider
      value={{
        userPreferences,
        setUserPreferences: (userPreferences: UserPreferences) => {
          // TODO: For logged in users, here we could sync preferences to backend
          if (hasStorageConsent) {
            localStorage.setItem(
              USER_PREFERENCES_STORAGE_KEY,
              JSON.stringify(userPreferences)
            )
          }
          setUserPreferences(userPreferences)
        },
      }}
    >
      {children}
    </UserPreferencesContext.Provider>
  )
}

export const useUserPreferences = () => useContext(UserPreferencesContext)
