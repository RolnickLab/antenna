import { REJECT_OPTIONS } from './constants'

type IdentificationData = {
  label: string
  details?: string
  value: string
}

const RECENT_IDENTIFICATIONS_STORAGE_KEY = 'ami-recent-identifications'
const DISPLAY_LIST_SIZE = 3
const STORAGE_LIST_SIZE = 5

const getRecentIdentifications = () => {
  const storageValue = localStorage.getItem(RECENT_IDENTIFICATIONS_STORAGE_KEY)

  if (!storageValue) {
    return []
  }

  try {
    return JSON.parse(storageValue) as IdentificationData[]
  } catch {
    localStorage.removeItem(RECENT_IDENTIFICATIONS_STORAGE_KEY)
    return []
  }
}

const addRecentIdentification = (identification: IdentificationData) => {
  const identifications = [identification, ...getRecentIdentifications()]

  localStorage.setItem(
    RECENT_IDENTIFICATIONS_STORAGE_KEY,
    JSON.stringify(identifications.slice(0, STORAGE_LIST_SIZE))
  )
}

const removeRecentIdentification = (value: string) => {
  const identifications = getRecentIdentifications().filter(
    (i) => i.value !== value
  )

  localStorage.setItem(
    RECENT_IDENTIFICATIONS_STORAGE_KEY,
    JSON.stringify(identifications)
  )
}

export const useRecentIdentifications = () => {
  const recentIdentifications = getRecentIdentifications()

  return {
    recentIdentifications: recentIdentifications.slice(0, DISPLAY_LIST_SIZE),
    addRecentIdentification: (identification: IdentificationData) => {
      if (REJECT_OPTIONS.some((o) => o.value === identification.value)) {
        // Skip store identifications of type reject
        return
      }

      if (recentIdentifications.some((i) => i.value === identification.value)) {
        // If a similar identification is already stored, remove this first
        removeRecentIdentification(identification.value)
      }

      addRecentIdentification(identification)
    },
  }
}
