import { useUserPreferences } from './userPreferences/userPreferencesContext'

export const useColumnSettings = (
  tableKey: string,
  defaultSettings: { [columnKey: string]: boolean }
) => {
  const { userPreferences, setUserPreferences } = useUserPreferences()

  return {
    // Merge persisted choices over the defaults so a column added after a user last
    // customized this table (whose key is absent from their saved settings) still
    // picks up its default visibility instead of being silently dropped.
    columnSettings: {
      ...defaultSettings,
      ...userPreferences.columnSettings[tableKey],
    },
    setColumnSettings: (settings: { [columnKey: string]: boolean }) => {
      setUserPreferences({
        ...userPreferences,
        columnSettings: {
          ...(userPreferences.columnSettings ?? {}),
          [tableKey]: settings,
        },
      })
    },
  }
}
