import { buildTrackingJobPayload, toTrackingScope } from './tracking-job'

describe('buildTrackingJobPayload', () => {
  test('tracks one session through the post-processing job type', () => {
    expect(
      buildTrackingJobPayload({
        name: 'Night one',
        projectId: '3',
        requireFeatures: true,
        scope: { type: 'session', sessionId: '42' },
      })
    ).toEqual({
      delay: 0,
      job_type_key: 'post_processing',
      name: 'Night one',
      params: {
        task: 'tracking',
        config: { event_ids: [42], require_features: true },
      },
      project_id: 3,
    })
  })

  test('tracks a capture set and passes a threshold typed into the form', () => {
    expect(
      buildTrackingJobPayload({
        costThreshold: '0.35',
        name: 'Survey',
        projectId: '3',
        requireFeatures: false,
        scope: { type: 'captureSet', captureSetId: '7' },
      }).params.config
    ).toEqual({
      cost_threshold: 0.35,
      require_features: false,
      source_image_collection_id: 7,
    })
  })

  test('leaves the threshold to the server when the field is empty', () => {
    const { config } = buildTrackingJobPayload({
      costThreshold: '',
      projectId: '3',
      requireFeatures: true,
      scope: { type: 'session', sessionId: '42' },
    }).params

    expect(config).not.toHaveProperty('cost_threshold')
  })

  test('names the job after its scope when no name is given', () => {
    expect(
      buildTrackingJobPayload({
        name: '  ',
        projectId: '3',
        requireFeatures: true,
        scope: { type: 'session', sessionId: '42' },
      }).name
    ).toBe('Tracking session 42')
  })

  test('refuses an id or threshold the server would reject', () => {
    const base = { projectId: '3', requireFeatures: true }

    expect(() =>
      buildTrackingJobPayload({
        ...base,
        scope: { type: 'session', sessionId: 'abc' },
      })
    ).toThrow()
    expect(() =>
      buildTrackingJobPayload({
        ...base,
        costThreshold: '-1',
        scope: { type: 'session', sessionId: '42' },
      })
    ).toThrow()
  })
})

describe('toTrackingScope', () => {
  test('reads only the field for the chosen scope', () => {
    expect(
      toTrackingScope({
        captureSetId: '7',
        scopeType: 'session',
        sessionId: '42',
      })
    ).toEqual({ type: 'session', sessionId: '42' })
    expect(
      toTrackingScope({
        captureSetId: '7',
        scopeType: 'captureSet',
        sessionId: '42',
      })
    ).toEqual({ type: 'captureSet', captureSetId: '7' })
  })

  test('is undefined until the chosen field is filled in', () => {
    expect(
      toTrackingScope({ scopeType: 'captureSet', sessionId: '42' })
    ).toBeUndefined()
  })
})
