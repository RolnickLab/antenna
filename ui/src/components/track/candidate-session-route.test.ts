import { getCandidateSessionRoute } from './candidate-session-route'

describe('candidate session route', () => {
  test('selects both occurrences and opens the candidate frame', () => {
    expect(
      getCandidateSessionRoute({
        captureId: '55',
        occurrenceIds: ['1', '2'],
        sessionRoute: '/projects/9/sessions/4',
      })
    ).toBe('/projects/9/sessions/4?occurrence=1&occurrence=2&capture=55')
  })
})
