import { ReactNode, createContext, useContext, useState } from 'react'
import { COOKIE_PREFERENCES_STORAGE_KEY, DEFAULT_SETTINGS } from './constants'
import { CookieContextValues, CookiePreferences, CookieSettings } from './types'

export const CookieContext = createContext<CookieContextValues>({
  settings: DEFAULT_SETTINGS,
  setSettings: () => {},
})

export const CookieContextProvider = ({
  children,
}: {
  children: ReactNode
}) => {
  const [preferences, setPreferences] = useState<CookiePreferences>(() => {
    const defaultPreferences = {
      settings: DEFAULT_SETTINGS,
    }
    const storedPreferences = localStorage.getItem(
      COOKIE_PREFERENCES_STORAGE_KEY
    )
    if (!storedPreferences) {
      return defaultPreferences
    }
    try {
      return JSON.parse(storedPreferences) as CookiePreferences
    } catch {
      return defaultPreferences
    }
  })

  return (
    <CookieContext.Provider
      value={{
        accepted: preferences.accepted,
        settings: preferences.settings,
        setSettings: (settings: CookieSettings) => {
          const preferences = {
            accepted: new Date().toISOString(),
            settings,
          }
          localStorage.setItem(
            COOKIE_PREFERENCES_STORAGE_KEY,
            JSON.stringify(preferences)
          )
          setPreferences(preferences)
        },
      }}
    >
      {children}
    </CookieContext.Provider>
  )
}

export const useCookieContext = () => useContext(CookieContext)
