import { renderHook, waitFor } from '@testing-library/react'
import { API_ROUTES, API_URL } from 'data-services/constants'
import nock from 'nock'
import { AppMock, queryClient } from 'utils/test'
import { AUTH_TOKEN_STORAGE_KEY } from 'utils/user/constants'
import { useMe } from '../useMe'

describe('useMe', () => {
  test('will return user info on success', async () => {
    // Prep
    nock(API_URL)
      .get(`/${API_ROUTES.ME}/`)
      .reply(200, { email: 'user@insectai.org' })

    // Run
    const { result } = renderHook(() => useMe(), { wrapper: AppMock })
    await waitFor(() => expect(result.current.user).toBeDefined())

    // Check
    expect(result.current.user).toEqual({
      email: 'user@insectai.org',
    })
  })

  test('will logout the user on 403 error', async () => {
    // Prep
    nock(API_URL).get(`/${API_ROUTES.ME}/`).times(2).reply(403)
    localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, 'example-token') // Simulate logged in user
    const removeQueriesSpy = jest.spyOn(queryClient, 'removeQueries')

    // Run
    const { result } = renderHook(() => useMe(), { wrapper: AppMock })
    await waitFor(() => expect(result.current.error).not.toBeNull())

    // Check
    expect(localStorage.getItem(AUTH_TOKEN_STORAGE_KEY)).toBeNull()
    expect(removeQueriesSpy).toBeCalledTimes(1)
  })

  test('will keep the user logged in on error !== 403', async () => {
    // Prep
    nock(API_URL).get(`/${API_ROUTES.ME}/`).times(2).reply(500)
    localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, 'example-token') // Simulate logged in user
    const removeQueriesSpy = jest.spyOn(queryClient, 'removeQueries')

    // Run
    const { result } = renderHook(() => useMe(), { wrapper: AppMock })
    await waitFor(() => expect(result.current.error).not.toBeNull())

    // Check
    expect(localStorage.getItem(AUTH_TOKEN_STORAGE_KEY)).toEqual(
      'example-token'
    )
    expect(removeQueriesSpy).toBeCalledTimes(0)
  })
})
