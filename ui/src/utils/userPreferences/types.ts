export interface UserPreferences {
  columnSettings: { [tableKey: string]: { [columnKey: string]: boolean } }
  recentIdentifications: {
    details?: string
    label: string
    value: string
  }[]
  termsMessageSeen?: boolean
}

export interface UserPreferencesContextValues {
  userPreferences: UserPreferences
  setUserPreferences: (userPreferences: UserPreferences) => void
}
