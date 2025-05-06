import { renderHook, waitFor } from '@testing-library/react'
import _axios from 'axios'
import { AppMock, queryClient } from 'utils/testHelpers'
import { AUTH_TOKEN_STORAGE_KEY } from 'utils/user/constants'
import { useUserInfo } from '../useUserInfo'

const axios = _axios as any

describe('useUserInfo', () => {
  afterEach(() => {
    jest.restoreAllMocks()
    jest.clearAllMocks()
  })

  test('will return user info on success', async () => {
    // Prep
    axios.get.mockImplementation(() =>
      Promise.resolve({ data: { id: 1, email: 'user@insectai.org' } })
    )
    localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, 'example-token') // Simulate logged in user

    // Run
    const { result } = renderHook(() => useUserInfo(), { wrapper: AppMock })
    await waitFor(() => expect(result.current.userInfo).toBeDefined())

    // Check
    expect(result.current.userInfo).toEqual({
      id: '1',
      email: 'user@insectai.org',
    })
  })

  test('will logout the user on 403 error', async () => {
    // Prep
    axios.get.mockImplementation(() =>
      Promise.reject({ response: { status: 403 } })
    )
    localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, 'example-token') // Simulate logged in user
    const removeQueriesSpy = jest.spyOn(queryClient, 'removeQueries')

    // Run
    const { result } = renderHook(() => useUserInfo(), { wrapper: AppMock })
    await waitFor(() => expect(result.current.userInfo).toBeUndefined())

    // Check
    expect(localStorage.getItem(AUTH_TOKEN_STORAGE_KEY)).toBeNull()
    expect(removeQueriesSpy).toHaveBeenCalled()
  })

  test('will keep the user logged in on error !== 403', async () => {
    // Prep
    axios.get.mockImplementation(() =>
      Promise.reject({ response: { status: 500 } })
    )
    localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, 'example-token') // Simulate logged in user
    const removeQueriesSpy = jest.spyOn(queryClient, 'removeQueries')

    // Run
    const { result } = renderHook(() => useUserInfo(), { wrapper: AppMock })
    await waitFor(() => expect(result.current.error).not.toBeNull())

    // Check
    expect(localStorage.getItem(AUTH_TOKEN_STORAGE_KEY)).toEqual(
      'example-token'
    )
    expect(removeQueriesSpy).toHaveBeenCalledTimes(0)
  })
})
