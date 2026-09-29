import { PathFrame } from 'data-services/models/occurrence-path'
import { buildTrail, MAX_GHOST_BOXES } from './ghost-trail'

const path = (length: number): PathFrame[] =>
  Array.from({ length }, (_, index) => ({
    bbox: [10 + index, 10, 40 + index, 40],
    captureHeight: 200,
    captureId: `c${index}`,
    captureWidth: 300,
    cropUrl: `https://example.test/${index}.jpg`,
    detectionId: `d${index}`,
    timestamp: new Date(2026, 8, 1, 22, index),
  }))

const byId = (frames: PathFrame[], captureId: string) =>
  buildTrail(frames, captureId)

describe('buildTrail', () => {
  it('never draws a path frame solid, so only the capture on screen looks live', () => {
    const { ghosts } = byId(path(20), 'c10')

    expect(ghosts.length).toBeGreaterThan(0)
    ghosts.forEach((ghost) => expect(ghost.opacity).toBeLessThan(1))
  })

  it('fades a frame further from the capture on screen than its neighbour', () => {
    const { ghosts } = byId(path(20), 'c10')
    const near = ghosts.find((ghost) => ghost.distance === 1)
    const far = ghosts.find((ghost) => ghost.distance === 5)

    expect(near && far && near.opacity > far.opacity).toBe(true)
  })

  it('holds the fade at a floor, so the furthest frame drawn is still visible', () => {
    const { ghosts } = byId(path(20), 'c10')

    ghosts.forEach((ghost) => expect(ghost.opacity).toBeGreaterThanOrEqual(0.2))
  })

  it('stacks a nearer frame over a further one', () => {
    const { ghosts } = byId(path(20), 'c10')
    const near = ghosts.find((ghost) => ghost.distance === 1)
    const far = ghosts.find((ghost) => ghost.distance === 5)

    expect(near && far && near.zIndex > far.zIndex).toBe(true)
  })

  it('leaves the frame on screen to its own live box but still counts it as shown', () => {
    const { ghosts, shownCount } = byId(path(20), 'c10')

    expect(ghosts.map((ghost) => ghost.id)).not.toContain('d10')
    expect(shownCount).toBe(ghosts.length + 1)
  })

  it('draws no more neighbours than the cap either side of the capture on screen', () => {
    const { ghosts } = byId(path(40), 'c20')

    expect(ghosts).toHaveLength(MAX_GHOST_BOXES)
    ghosts.forEach((ghost) =>
      expect(ghost.distance).toBeLessThanOrEqual(MAX_GHOST_BOXES / 2)
    )
  })

  it('numbers a frame by its place in the whole track, not in the part drawn', () => {
    const { ghosts, total } = byId(path(40), 'c20')
    const first = ghosts[0]

    expect(total).toBe(40)
    // The first box drawn is eight frames back, so it is the thirteenth of forty.
    expect(first.position).toBe(13)
  })

  it('separates the frames before the capture on screen from the ones after', () => {
    const { ghosts } = byId(path(20), 'c10')

    expect(ghosts.find((ghost) => ghost.id === 'd9')?.isEarlier).toBe(true)
    expect(ghosts.find((ghost) => ghost.id === 'd11')?.isEarlier).toBe(false)
  })

  it('treats every frame as a ghost when the capture on screen holds none', () => {
    const { ghosts, shownCount } = byId(path(6), 'elsewhere')

    expect(ghosts.map((ghost) => ghost.id)).toContain('d0')
    expect(shownCount).toBe(ghosts.length)
  })

  it('reads direction from the clock when no frame sits on the capture viewed', () => {
    // Extending a track puts the viewer on captures the track does not cover, so the
    // track's order cannot say which frames come before the one on screen.
    const viewed = new Date(2026, 8, 1, 22, 2, 30)
    const { ghosts } = buildTrail(path(5), 'elsewhere', viewed)

    expect(ghosts.find((ghost) => ghost.id === 'd1')?.isEarlier).toBe(true)
    expect(ghosts.find((ghost) => ghost.id === 'd4')?.isEarlier).toBe(false)
  })

  it('measures the gap from the capture being viewed, signed by direction', () => {
    const viewed = new Date(2026, 8, 1, 22, 2)
    const { ghosts } = buildTrail(path(5), 'c2', viewed)

    // The helper spaces frames a minute apart, so index 1 is a minute before the
    // capture on screen and index 4 is two minutes after it.
    expect(ghosts.find((ghost) => ghost.id === 'd1')?.offsetSeconds).toBe(-60)
    expect(ghosts.find((ghost) => ghost.id === 'd4')?.offsetSeconds).toBe(120)
  })

  it('reports no gap for a frame with no timestamp', () => {
    const frames = path(3)
    frames[0] = { ...frames[0], timestamp: null }
    const { ghosts } = buildTrail(frames, 'c1', new Date(2026, 8, 1, 22, 1))

    expect(ghosts.find((ghost) => ghost.id === 'd0')?.offsetSeconds).toBeNull()
  })

  it('reports no gap when the capture being viewed has no timestamp of its own', () => {
    const { ghosts } = byId(path(4), 'c1')

    ghosts.forEach((ghost) => expect(ghost.offsetSeconds).toBeNull())
  })

  it('keeps the fade under its ceiling when no frame sits on the capture viewed', () => {
    const { ghosts } = byId(path(6), 'elsewhere')

    expect(ghosts.length).toBeGreaterThan(0)
    ghosts.forEach((ghost) => {
      expect(ghost.opacity).toBeLessThanOrEqual(0.75)
      expect(ghost.distance).toBeGreaterThanOrEqual(1)
    })
  })
})
