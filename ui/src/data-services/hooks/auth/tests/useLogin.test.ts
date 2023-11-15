import { renderHook, waitFor } from '@testing-library/react'
import { AppMock, queryClient } from 'utils/testHelpers'
import { AUTH_TOKEN_STORAGE_KEY } from 'utils/user/constants'
import { useLogin } from '../useLogin'

const axios: any = require('axios')

describe('useLogin', () => {
  afterEach(() => {
    jest.restoreAllMocks()
    jest.clearAllMocks()
  })

  test('will login user on success', async () => {
    axios.post.mockImplementation(() =>
      Promise.resolve({ data: { auth_token: 'example-token-from-api' } })
    )
    const removeQueriesSpy = jest.spyOn(queryClient, 'removeQueries')

    // Run
    const { result } = renderHook(() => useLogin(), { wrapper: AppMock })
    result.current.login({ email: 'user@insectai.org', password: 'password ' })
    await waitFor(() => expect(result.current.isSuccess).toEqual(true))

    // Check
    expect(localStorage.getItem(AUTH_TOKEN_STORAGE_KEY)).toEqual(
      'example-token-from-api'
    )
    expect(removeQueriesSpy).toHaveBeenCalledTimes(1)
  })
})
