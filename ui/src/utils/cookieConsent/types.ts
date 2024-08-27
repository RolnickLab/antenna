export enum CookieCategory {
  Necessary = 'necessary',
  Functionality = 'functionality',
  Performance = 'performance',
}

export type CookieSettings = { [key in CookieCategory]: boolean }

export interface CookieConsent {
  settings: CookieSettings
  accepted?: string
}

export interface CookieConsentContextValues {
  accepted?: string
  settings: CookieSettings
  setSettings: (settings: CookieSettings) => void
}
