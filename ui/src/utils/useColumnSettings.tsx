import { useUserPreferences } from './userPreferences/userPreferencesContext'

export const useColumnSettings = (
  tableKey: string,
  defaultSettings: { [columnKey: string]: boolean }
) => {
  const { userPreferences, setUserPreferences } = useUserPreferences()

  return {
    columnSettings: userPreferences.columnSettings[tableKey] ?? defaultSettings,
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
