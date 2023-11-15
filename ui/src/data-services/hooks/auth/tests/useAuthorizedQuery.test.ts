import { renderHook, waitFor } from '@testing-library/react'
import { API_URL } from 'data-services/constants'
import { AppMock } from 'utils/testHelpers'
import { AUTH_TOKEN_STORAGE_KEY } from 'utils/user/constants'
import { useAuthorizedQuery } from '../useAuthorizedQuery'

const axios: any = require('axios')

const EXAMPLE_URL = `${API_URL}/ping/`

describe('useAuthorizedQuery', () => {
  beforeAll(() => {
    axios.get.mockImplementation(() => Promise.resolve({ data: 'pong' }))
  })
  afterAll(() => {
    jest.restoreAllMocks()
    jest.clearAllMocks()
  })

  test('will pass auth header if user is logged in', async () => {
    localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, 'example-token') // Simulate logged in user
    const axiosGetSpy = jest.spyOn(axios, 'get')

    const { result } = renderHook(
      () =>
        useAuthorizedQuery({
          url: EXAMPLE_URL,
        }),
      { wrapper: AppMock }
    )
    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(axiosGetSpy).toHaveBeenCalledWith(EXAMPLE_URL, {
      headers: { Authorization: 'Token example-token' },
    })
  })

  test('will not pass auth header if user is logged out', async () => {
    localStorage.clear() // Simulate logged out user
    const axiosGetSpy = jest.spyOn(axios, 'get')

    const { result } = renderHook(
      () =>
        useAuthorizedQuery({
          url: EXAMPLE_URL,
        }),
      { wrapper: AppMock }
    )
    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(axiosGetSpy).toHaveBeenCalledWith(EXAMPLE_URL, {
      headers: undefined,
    })
  })
})
