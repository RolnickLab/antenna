import { renderHook, waitFor } from '@testing-library/react'
import { API_ROUTES, API_URL } from 'data-services/constants'
import nock from 'nock'
import { AppMock, queryClient } from 'utils/test'
import { AUTH_TOKEN_STORAGE_KEY } from 'utils/user/constants'
import { useUser } from 'utils/user/userContext'
import { useLogout } from '../useLogout'

const useTestLogout = () => {
  const { user } = useUser()
  const { logout, isSuccess, error } = useLogout()
  return { user, logout, isSuccess, error }
}

describe('useLogout', () => {
  test('will logout user on success', async () => {
    // Prep
    nock(API_URL)
      .post(`/${API_ROUTES.LOGOUT}/`)
      .reply(200, { auth_token: 'example-token-from-api' })
    localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, 'example-token') // Simulate logged in user
    const removeQueriesSpy = jest.spyOn(queryClient, 'removeQueries')

    // Run
    const { result } = renderHook(() => useTestLogout(), { wrapper: AppMock })
    result.current.logout()
    await waitFor(() => expect(result.current.isSuccess).toEqual(true))

    // Check
    expect(localStorage.getItem(AUTH_TOKEN_STORAGE_KEY)).toBeNull()
    expect(removeQueriesSpy).toBeCalledTimes(1)
  })

  test('will logout user on 403 error', async () => {
    // Prep
    nock(API_URL).post(`/${API_ROUTES.LOGOUT}/`).reply(403)
    localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, 'example-token') // Simulate logged in user
    const removeQueriesSpy = jest.spyOn(queryClient, 'removeQueries')

    // Run
    const { result } = renderHook(() => useTestLogout(), { wrapper: AppMock })
    result.current.logout()
    await waitFor(() => expect(result.current.error).not.toBeNull())

    // Check
    expect(localStorage.getItem(AUTH_TOKEN_STORAGE_KEY)).toBeNull()
    expect(removeQueriesSpy).toBeCalledTimes(1)
  })

  test('will keep the user logged in on error !== 403', async () => {
    // Prep
    nock(API_URL).post(`/${API_ROUTES.LOGOUT}/`).reply(500)
    localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, 'example-token') // Simulate logged in user
    const removeQueriesSpy = jest.spyOn(queryClient, 'removeQueries')

    // Run
    const { result } = renderHook(() => useTestLogout(), { wrapper: AppMock })
    result.current.logout()
    await waitFor(() => expect(result.current.error).not.toBeNull())

    // Check
    expect(localStorage.getItem(AUTH_TOKEN_STORAGE_KEY)).toEqual(
      'example-token'
    )
    expect(removeQueriesSpy).toBeCalledTimes(0)
  })
})
