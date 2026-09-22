import { buildDetectionLink } from './useActiveDetection'

const BASE = 'http://example.test/projects/1/sessions/2'

describe('buildDetectionLink', () => {
  it('keeps the capture already in the link, so the detection can be found', () => {
    const link = buildDetectionLink(`${BASE}?capture=55`, '901')

    expect(link).toContain('capture=55')
    expect(link).toContain('detection=901')
  })

  it('points an existing detection link at a different detection', () => {
    const link = buildDetectionLink(`${BASE}?capture=55&detection=111`, '222')

    expect(link).toContain('detection=222')
    expect(link).not.toContain('detection=111')
  })

  it('adds the detection to a link that carries none', () => {
    expect(buildDetectionLink(BASE, '901')).toContain('detection=901')
  })

  it('leaves the rest of the link alone', () => {
    // The occurrence stays on the link: it says which track held the detection when the
    // link was made, which is worth keeping even though the detection is what resolves it.
    const link = buildDetectionLink(`${BASE}?capture=55&occurrence=77`, '901')

    expect(link).toContain('occurrence=77')
    expect(link).toContain(`${BASE}`)
  })
})
