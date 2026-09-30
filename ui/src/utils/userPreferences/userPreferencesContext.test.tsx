import { act, renderHook } from '@testing-library/react'
import { ReactNode } from 'react'
import { CookieConsentContext } from 'utils/cookieConsent/cookieConsentContext'
import { DEFAULT_SETTINGS } from 'utils/cookieConsent/constants'
import { USER_PREFERENCES_STORAGE_KEY } from './constants'
import {
  UserPreferencesContextProvider,
  useUserPreferences,
} from './userPreferencesContext'

const wrapper = ({ children }: { children: ReactNode }) => (
  <CookieConsentContext.Provider
    value={{
      accepted: '2026-01-01T00:00:00Z',
      settings: { ...DEFAULT_SETTINGS, functionality: true },
      setSettings: () => {},
    }}
  >
    <UserPreferencesContextProvider>{children}</UserPreferencesContextProvider>
  </CookieConsentContext.Provider>
)

describe('useUserPreferences', () => {
  beforeEach(() => localStorage.clear())
  afterEach(() => jest.restoreAllMocks())

  test('path crops are off until the viewer turns them on, and stay on', () => {
    const first = renderHook(() => useUserPreferences(), { wrapper })
    expect(first.result.current.userPreferences.showPathCrops).toBe(false)

    act(() =>
      first.result.current.setUserPreferences({
        ...first.result.current.userPreferences,
        showPathCrops: true,
      })
    )

    const second = renderHook(() => useUserPreferences(), { wrapper })
    expect(second.result.current.userPreferences.showPathCrops).toBe(true)
  })

  test('storage that throws falls back to defaults and still applies changes', () => {
    localStorage.setItem(
      USER_PREFERENCES_STORAGE_KEY,
      JSON.stringify({ showPathCrops: true })
    )
    jest
      .spyOn(Object.getPrototypeOf(window.localStorage), 'getItem')
      .mockImplementation(() => {
        throw new Error('blocked')
      })
    jest
      .spyOn(Object.getPrototypeOf(window.localStorage), 'setItem')
      .mockImplementation(() => {
        throw new Error('blocked')
      })

    const { result } = renderHook(() => useUserPreferences(), { wrapper })
    expect(result.current.userPreferences.showPathCrops).toBe(false)

    act(() =>
      result.current.setUserPreferences({
        ...result.current.userPreferences,
        showPathCrops: true,
      })
    )
    expect(result.current.userPreferences.showPathCrops).toBe(true)
  })
})
