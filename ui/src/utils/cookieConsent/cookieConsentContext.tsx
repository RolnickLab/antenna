import { ReactNode, createContext, useContext, useState } from 'react'
import { COOKIE_CONSENT_STORAGE_KEY, DEFAULT_SETTINGS } from './constants'
import {
  CookieConsent,
  CookieConsentContextValues,
  CookieSettings,
} from './types'

export const CookieConsentContext = createContext<CookieConsentContextValues>({
  settings: DEFAULT_SETTINGS,
  setSettings: () => {},
})

export const CookieConsentContextProvider = ({
  children,
}: {
  children: ReactNode
}) => {
  const [consent, setConsent] = useState<CookieConsent>(() => {
    const defaultPreferences = {
      settings: DEFAULT_SETTINGS,
    }
    const storedPreferences = localStorage.getItem(COOKIE_CONSENT_STORAGE_KEY)
    if (!storedPreferences) {
      return defaultPreferences
    }
    try {
      return JSON.parse(storedPreferences) as CookieConsent
    } catch {
      return defaultPreferences
    }
  })

  return (
    <CookieConsentContext.Provider
      value={{
        accepted: consent.accepted,
        settings: consent.settings,
        setSettings: (settings: CookieSettings) => {
          const consent = {
            accepted: new Date().toISOString(),
            settings,
          }
          localStorage.setItem(
            COOKIE_CONSENT_STORAGE_KEY,
            JSON.stringify(consent)
          )
          setConsent(consent)
        },
      }}
    >
      {children}
    </CookieConsentContext.Provider>
  )
}

export const useCookieConsent = () => useContext(CookieConsentContext)
