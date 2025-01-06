import { UserPreferences } from './types'

export const USER_PREFERENCES_STORAGE_KEY = 'ami-user-preferences'

export const DEFAULT_PREFERENCES: UserPreferences = {
  columnSettings: {},
  recentIdentifications: [],
  scoreThreshold: 0.6,
  termsMessageSeen: false,
}
