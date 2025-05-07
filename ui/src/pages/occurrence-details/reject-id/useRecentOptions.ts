import { useUserPreferences } from 'utils/userPreferences/userPreferencesContext'
import { REJECT_OPTIONS } from './constants'

const DISPLAY_LIST_SIZE = 5 // Limit how many identifications are displayed
const STORAGE_LIST_SIZE = 5 // Limit how many identifications are stored

export const useRecentIdentifications = () => {
  const {
    userPreferences,
    userPreferences: { recentIdentifications },
    setUserPreferences,
  } = useUserPreferences()

  return {
    recentIdentifications: recentIdentifications.slice(0, DISPLAY_LIST_SIZE),
    addRecentIdentification: (identification: {
      label: string
      details?: string
      value: string
    }) => {
      if (REJECT_OPTIONS.some((o) => o.value === identification.value)) {
        // Do not add if identification is of type reject
        return
      }

      setUserPreferences({
        ...userPreferences,
        recentIdentifications: [
          identification,
          ...recentIdentifications.filter(
            (i) => i.value !== identification.value // To avoid identification duplicates
          ),
        ].slice(0, STORAGE_LIST_SIZE),
      })
    },
  }
}
