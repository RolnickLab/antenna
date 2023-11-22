import { act, renderHook } from '@testing-library/react'
import { AppMock, queryClient } from 'utils/testHelpers'
import { AUTH_TOKEN_STORAGE_KEY } from './constants'
import { useUser } from './userContext'

describe('useUser', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  afterEach(() => {
    jest.restoreAllMocks()
    jest.clearAllMocks()
  })

  test('will start as logged out as default', () => {
    const { result } = renderHook(() => useUser(), { wrapper: AppMock })

    expect(result.current.user).toEqual({
      loggedIn: false,
    })
  })

  test('will start as logged in, if local storage has token', () => {
    localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, 'example-token')

    const { result } = renderHook(() => useUser(), { wrapper: AppMock })

    expect(result.current.user).toEqual({
      loggedIn: true,
      token: 'example-token',
    })
  })

  test('will store token and change to logged in when token is set', () => {
    const { result } = renderHook(() => useUser(), { wrapper: AppMock })
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
    const { result } = renderHook(() => useUser(), { wrapper: AppMock })
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
    const removeQueriesSpy = jest.spyOn(queryClient, 'removeQueries')

    const { result } = renderHook(() => useUser(), { wrapper: AppMock })
    act(() => {
      result.current.setToken('example-token')
    })

    expect(removeQueriesSpy).toHaveBeenCalledTimes(1)
  })

  test('will remove queries after token is cleared', () => {
    const removeQueriesSpy = jest.spyOn(queryClient, 'removeQueries')

    const { result } = renderHook(() => useUser(), { wrapper: AppMock })
    act(() => {
      result.current.clearToken()
    })

    expect(removeQueriesSpy).toHaveBeenCalledTimes(1)
  })
})
