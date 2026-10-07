import { Job, ServerJobType } from './job'

// The kit's entry point pulls in stylesheets, which Jest does not load.
jest.mock('nova-ui-kit', () => ({
  CONSTANTS: jest.requireActual('nova-ui-kit/constants').CONSTANTS,
}))

describe('Job.getJobTypeInfo', () => {
  test('labels a post-processing job', () => {
    expect(Job.getJobTypeInfo('post_processing').label).toBe('Post-processing')
  })

  test("falls back to the server's name for a type it does not know", () => {
    const key = 'future_type' as ServerJobType

    expect(Job.getJobTypeInfo(key, 'Future type').label).toBe('Future type')
    expect(Job.getJobTypeInfo(key).label).toBe('future_type')
  })
})
