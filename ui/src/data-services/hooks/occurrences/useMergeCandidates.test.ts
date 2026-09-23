import {
  getCandidatesEmptyMessage,
  getDetectionError,
  getMergeCandidatesParams,
  getServerMessage,
  shouldRetryCandidates,
} from './useMergeCandidates'

describe('getMergeCandidatesParams', () => {
  test('searches minutes around the occurrence by default', () => {
    expect(`${getMergeCandidatesParams({ projectId: '5' })}`).toBe(
      'project_id=5&minutes=5'
    )
  })

  test('a capture scope replaces the minutes window', () => {
    expect(
      `${getMergeCandidatesParams({
        captures: 3,
        minutes: 30,
        projectId: '5',
      })}`
    ).toBe('project_id=5&captures=3')
  })

  test('ranks against a detection when one is given', () => {
    expect(
      `${getMergeCandidatesParams({
        captures: 3,
        detectionId: '42',
        projectId: '5',
      })}`
    ).toBe('project_id=5&detection=42&captures=3')
  })
})

describe('getDetectionError', () => {
  const badRequest = (detection: unknown) => ({
    response: { data: { detection } },
  })

  test('reads the reason as a string or the first of a list', () => {
    expect(getDetectionError(badRequest('Not in this occurrence.'))).toBe(
      'Not in this occurrence.'
    )
    expect(getDetectionError(badRequest(['Has no box.', 'Other.']))).toBe(
      'Has no box.'
    )
  })

  test('is undefined for other errors', () => {
    expect(getDetectionError(undefined)).toBeUndefined()
    expect(getDetectionError({ response: { data: { detail: 'x' } } })).toBe(
      undefined
    )
    expect(getDetectionError(badRequest([]))).toBeUndefined()
  })
})

describe('getCandidatesEmptyMessage', () => {
  test('tells a failed request apart from an empty scope', () => {
    const empty = getCandidatesEmptyMessage(undefined)
    const failed = getCandidatesEmptyMessage({ response: { status: 500 } })

    expect(failed).not.toBe(empty)
    expect(
      getCandidatesEmptyMessage({
        response: { data: { detection: 'Has no box.' } },
      })
    ).toBe('Has no box.')
  })
})

describe('shouldRetryCandidates', () => {
  const failed = (status?: number) => ({ response: { status } })

  test('does not retry an answer that asking again cannot change', () => {
    for (const status of [401, 403, 404]) {
      expect(shouldRetryCandidates(0, failed(status))).toBe(false)
    }
  })

  test('retries other failures a few times', () => {
    expect(shouldRetryCandidates(0, failed(500))).toBe(true)
    expect(shouldRetryCandidates(0, new Error('Network Error'))).toBe(true)
    expect(shouldRetryCandidates(3, failed(500))).toBe(false)
  })
})

describe('getServerMessage', () => {
  test("shows the server's reason", () => {
    const error = {
      message: 'Request failed with status code 403',
      response: { data: { detail: 'Tracking is not enabled.' } },
    }

    expect(getServerMessage(error)).toBe('Tracking is not enabled.')
    expect(getCandidatesEmptyMessage(error)).toBe('Tracking is not enabled.')
  })

  test('reads a field error when there is no general one', () => {
    expect(
      getServerMessage({
        message: 'Request failed with status code 400',
        response: { data: { minutes: ['Must be positive.'] } },
      })
    ).toBe('Must be positive.')
  })

  test('is undefined when the response carries no reason', () => {
    expect(getServerMessage(undefined)).toBeUndefined()
    expect(
      getServerMessage({
        message: 'Request failed with status code 500',
        response: { data: '<html>Server error</html>' },
      })
    ).toBeUndefined()
  })
})
