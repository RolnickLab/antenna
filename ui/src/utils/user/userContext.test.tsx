import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook } from '@testing-library/react'
import { ReactNode } from 'react'
import { AUTH_TOKEN_STORAGE_KEY } from './constants'
import { UserContextProvider, useUser } from './userContext'

// Mock local storage
class LocalStorageMock {
  store: { [key: string]: string } = {}

  clear() {
    this.store = {}
  }

  getItem(key: string) {
    return this.store[key] || null
  }

  setItem(key: string, value: string) {
    this.store[key] = String(value)
  }

  removeItem(key: string) {
    delete this.store[key]
  }
}

global.localStorage = new LocalStorageMock() as any

// Mock app
const queryClient = new QueryClient()

const wrapper = ({ children }: { children: ReactNode }) => (
  <QueryClientProvider client={queryClient as any}>
    <UserContextProvider>{children}</UserContextProvider>
  </QueryClientProvider>
)

describe('useUser', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  test('will start as logged out as default', () => {
    const { result } = renderHook(() => useUser(), { wrapper })

    expect(result.current.user).toEqual({
      loggedIn: false,
    })
  })

  test('will start as logged in, if local storage has token', () => {
    localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, 'example-token')

    const { result } = renderHook(() => useUser(), { wrapper })

    expect(result.current.user).toEqual({
      loggedIn: true,
      token: 'example-token',
    })
  })

  test('will store token and change to logged in when token is set', () => {
    const { result } = renderHook(() => useUser(), { wrapper })

    act(() => {
      result.current.setToken('example-token')
    })

    expect(localStorage.getItem(AUTH_TOKEN_STORAGE_KEY)).toEqual(
      'example-token'
    )

    expect(result.current.user).toEqual({
      loggedIn: true,
      token: 'example-token',
    })
  })

  test('will remove token from storage and change to logged out when token is cleared', () => {
    const { result } = renderHook(() => useUser(), { wrapper })

    act(() => {
      result.current.setToken('example-token')
      result.current.clearToken()
    })

    expect(localStorage.getItem(AUTH_TOKEN_STORAGE_KEY)).toBeNull()

    expect(result.current.user).toEqual({
      loggedIn: false,
      token: undefined,
    })
  })

  test('will remove queries after token is set', () => {
    const spy = jest.spyOn(queryClient, 'removeQueries')

    const { result } = renderHook(() => useUser(), { wrapper })

    act(() => {
      result.current.setToken('example-token')
    })

    expect(spy).toBeCalledTimes(1)
  })

  test('will remove queries after token is cleared', () => {
    const spy = jest.spyOn(queryClient, 'removeQueries')

    const { result } = renderHook(() => useUser(), { wrapper })

    act(() => {
      result.current.clearToken()
    })

    expect(spy).toBeCalledTimes(1)
  })
})
