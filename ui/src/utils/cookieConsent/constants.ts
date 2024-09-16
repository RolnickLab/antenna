import { CookieCategory, CookieSettings } from './types'

export const COOKIE_CONSENT_STORAGE_KEY = 'ami-cookie-consent'

export const DEFAULT_SETTINGS: CookieSettings = {
  [CookieCategory.Necessary]: true,
  [CookieCategory.Functionality]: false,
  [CookieCategory.Performance]: false,
}
