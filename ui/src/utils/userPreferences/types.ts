export interface UserPreferences {
  columnSettings: { [tableKey: string]: { [columnKey: string]: boolean } }
  recentIdentifications: {
    details?: string
    label: string
    value: string
  }[]
  /** Fill the boxes along a track's path with each frame's crop, not just an outline. */
  showPathCrops?: boolean
  termsMessageSeen?: boolean
}

export interface UserPreferencesContextValues {
  userPreferences: UserPreferences
  setUserPreferences: (userPreferences: UserPreferences) => void
}
