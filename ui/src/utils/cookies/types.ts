export enum CookieCategory {
  Necessary = 'necessary',
  Functionality = 'functionality',
  Performance = 'performance',
}

export type CookieSettings = { [key in CookieCategory]: boolean }

export interface CookiePreferences {
  settings: CookieSettings
  accepted?: string
}

export interface CookieContextValues {
  accepted?: string
  settings: CookieSettings
  setSettings: (settings: CookieSettings) => void
}
