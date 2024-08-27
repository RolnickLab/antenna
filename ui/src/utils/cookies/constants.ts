import { CookieCategory, CookieSettings } from './types'

export const COOKIE_PREFERENCES_STORAGE_KEY = 'ami-cookie-preferences'

export const DEFAULT_SETTINGS: CookieSettings = {
  [CookieCategory.Necessary]: true,
  [CookieCategory.Functionality]: false,
  [CookieCategory.Performance]: false,
}
