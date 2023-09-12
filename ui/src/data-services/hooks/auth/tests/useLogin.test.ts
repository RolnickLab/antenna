import { renderHook, waitFor } from '@testing-library/react'
import { API_ROUTES, API_URL } from 'data-services/constants'
import nock from 'nock'
import { AppMock, queryClient } from 'utils/test'
import { AUTH_TOKEN_STORAGE_KEY } from 'utils/user/constants'
import { useLogin } from '../useLogin'

describe('useLogin', () => {
  test('will login user on success', async () => {
    // Prep
    nock(API_URL)
      .post(`/${API_ROUTES.LOGIN}/`)
      .reply(200, { auth_token: 'example-token-from-api' })
    const removeQueriesSpy = jest.spyOn(queryClient, 'removeQueries')

    // Run
    const { result } = renderHook(() => useLogin(), { wrapper: AppMock })
    result.current.login({ email: 'user@insectai.org', password: 'password ' })
    await waitFor(() => expect(result.current.isSuccess).toEqual(true))

    // Check
    expect(localStorage.getItem(AUTH_TOKEN_STORAGE_KEY)).toEqual(
      'example-token-from-api'
    )
    expect(removeQueriesSpy).toBeCalledTimes(1)
  })
})
