import {
  getCandidatesEmptyMessage,
  getDetectionError,
  getMergeCandidatesParams,
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
