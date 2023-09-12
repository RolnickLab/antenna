import { renderHook, waitFor } from '@testing-library/react'
import axios from 'axios'
import { API_URL } from 'data-services/constants'
import nock from 'nock'
import { AppMock } from 'utils/test'
import { AUTH_TOKEN_STORAGE_KEY } from 'utils/user/constants'
import { useAuthorizedQuery } from '../useAuthorizedQuery'

const EXAMPLE_URL = `${API_URL}/ping/`

describe('useAuthorizedQuery', () => {
  beforeAll(() => {
    nock(API_URL).get('/ping/').reply(200)
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

    expect(axiosGetSpy).toBeCalledWith(EXAMPLE_URL, {
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

    expect(axiosGetSpy).toBeCalledWith(EXAMPLE_URL, { heders: undefined })
  })
})
