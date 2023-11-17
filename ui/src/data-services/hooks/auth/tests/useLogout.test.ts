import { renderHook, waitFor } from '@testing-library/react'
import _axios from 'axios'
import { AppMock, queryClient } from 'utils/testHelpers'
import { AUTH_TOKEN_STORAGE_KEY } from 'utils/user/constants'
import { useLogout } from '../useLogout'

const axios = _axios as any

describe('useLogout', () => {
  afterEach(() => {
    jest.restoreAllMocks()
    jest.clearAllMocks()
  })

  test('will logout user on success', async () => {
    // Prep
    axios.post.mockImplementation(() =>
      Promise.resolve({ data: { auth_token: 'example-token-from-api' } })
    )
    localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, 'example-token') // Simulate logged in user
    const removeQueriesSpy = jest.spyOn(queryClient, 'removeQueries')

    // Run
    const { result } = renderHook(() => useLogout(), { wrapper: AppMock })
    result.current.logout()
    await waitFor(() => expect(result.current.isSuccess).toEqual(true))

    // Check
    expect(localStorage.getItem(AUTH_TOKEN_STORAGE_KEY)).toBeNull()
    expect(removeQueriesSpy).toHaveBeenCalledTimes(1)
  })

  test('will logout user on 403 error', async () => {
    // Prep
    axios.post.mockImplementation(() =>
      Promise.reject({ response: { status: 403 } })
    )
    localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, 'example-token') // Simulate logged in user
    const removeQueriesSpy = jest.spyOn(queryClient, 'removeQueries')

    // Run
    const { result } = renderHook(() => useLogout(), { wrapper: AppMock })
    result.current.logout()
    await waitFor(() => expect(result.current.error).not.toBeNull())

    // Check
    expect(localStorage.getItem(AUTH_TOKEN_STORAGE_KEY)).toBeNull()
    expect(removeQueriesSpy).toHaveBeenCalledTimes(1)
  })

  test('will keep the user logged in on error !== 403', async () => {
    // Prep
    axios.post.mockImplementation(() =>
      Promise.reject({ response: { status: 500 } })
    )
    localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, 'example-token') // Simulate logged in user
    const removeQueriesSpy = jest.spyOn(queryClient, 'removeQueries')

    // Run
    const { result } = renderHook(() => useLogout(), { wrapper: AppMock })
    result.current.logout()
    await waitFor(() => expect(result.current.error).not.toBeNull())

    // Check
    expect(localStorage.getItem(AUTH_TOKEN_STORAGE_KEY)).toEqual(
      'example-token'
    )
    expect(removeQueriesSpy).toHaveBeenCalledTimes(0)
  })
})
