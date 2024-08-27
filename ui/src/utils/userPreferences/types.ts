export interface UserPreferences {
  recentIdentifications: {
    details?: string
    label: string
    value: string
  }[]
  scoreThreshold: number
}

export interface UserPreferencesContextValues {
  userPreferences: UserPreferences
  setUserPreferences: (userPreferences: UserPreferences) => void
}
