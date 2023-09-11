import { renderHook, waitFor } from '@testing-library/react'
import { API_ROUTES, API_URL } from 'data-services/constants'
import nock from 'nock'
import { AppMock } from 'utils/test'
import { useUser } from 'utils/user/userContext'
import { useLogin } from '../useLogin'

const useTestLogin = () => {
  const { user } = useUser()
  const { login, isSuccess } = useLogin()
  return { user, login, isSuccess }
}

describe('useLogin', () => {
  test('will login user on success', async () => {
    // Prep
    nock(API_URL)
      .post(`/${API_ROUTES.LOGIN}/`)
      .reply(200, { auth_token: 'example-token-from-api' })

    // Run
    const { result } = renderHook(() => useTestLogin(), { wrapper: AppMock })
    result.current.login({ email: 'user@insectai.org', password: 'password ' })
    await waitFor(() => expect(result.current.isSuccess).toEqual(true))

    // Check
    expect(result.current.user.loggedIn).toEqual(true)
    expect(result.current.user.token).toEqual('example-token-from-api')
  })
})
