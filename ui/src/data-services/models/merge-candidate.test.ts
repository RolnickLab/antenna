import {
  convertMergeCandidate,
  getComparisonSides,
  getDistanceLabel,
  getSimilarityLabel,
  getWhenLabel,
  isMergeable,
  MergeCandidate,
  ServerMergeCandidate,
  sortMergeCandidates,
} from './merge-candidate'

const serverCandidate = (
  overrides: Partial<ServerMergeCandidate>
): ServerMergeCandidate => ({
  id: 7,
  determination: { id: 3, name: 'Noctua pronuba' },
  detections_count: 4,
  first_appearance_timestamp: '2026-09-09T02:00:00',
  last_appearance_timestamp: '2026-09-09T02:03:00',
  relation: 'after',
  time_offset_seconds: 120,
  distance: 0.0123,
  similarity: 0.987,
  cost: 0.5,
  image: 'https://example.com/crop.jpg',
  capture_id: 11,
  image_timestamp: '2026-09-09T02:03:00',
  edge_image: 'https://example.com/edge.jpg',
  edge_timestamp: '2026-09-09T02:01:00',
  shared_captures: 0,
  ...overrides,
})

describe('merge candidate conversion', () => {
  test('names the row after its determination and carries one crop', () => {
    const candidate = convertMergeCandidate(serverCandidate({}))

    expect(candidate.id).toBe('7')
    expect(candidate.displayName).toBe('Noctua pronuba #7')
    expect(candidate.images).toEqual([{ src: 'https://example.com/crop.jpg' }])
    expect(candidate.numDetections).toBe(4)
  })

  test('a candidate without a determination or crop still renders', () => {
    const candidate = convertMergeCandidate(
      serverCandidate({ determination: null, image: null })
    )

    expect(candidate.displayName).toBe('#7')
    expect(candidate.images).toEqual([])
  })

  test('a candidate sharing a capture with the track cannot be merged', () => {
    const merge = (shared_captures: number) =>
      isMergeable(convertMergeCandidate(serverCandidate({ shared_captures })))

    expect(merge(1)).toBe(false)
    expect(merge(0)).toBe(true)
    expect(isMergeable({})).toBe(true)
  })
})

describe('comparison sides', () => {
  const candidateCrop = 'https://example.com/crop.jpg'
  const edgeCrop = 'https://example.com/edge.jpg'
  const srcs = (server: Partial<ServerMergeCandidate>) => {
    const sides = getComparisonSides(
      convertMergeCandidate(serverCandidate(server))
    )
    return [sides.left.src, sides.right.src, sides.gapLabel]
  }

  test('a "before" candidate sits on the left with a negative gap', () => {
    expect(srcs({ relation: 'before', time_offset_seconds: -40 })).toEqual([
      candidateCrop,
      edgeCrop,
      '−40 s',
    ])
  })

  test('an "after" candidate sits on the right with a positive gap', () => {
    expect(srcs({ relation: 'after', time_offset_seconds: 120 })).toEqual([
      edgeCrop,
      candidateCrop,
      '+2 min',
    ])
  })

  test('an overlapping candidate sits on the left and reads as overlapping', () => {
    expect(srcs({ relation: 'overlapping', time_offset_seconds: 0 })).toEqual([
      candidateCrop,
      edgeCrop,
      'Overlaps',
    ])
  })

  test('a missing edge crop leaves that side empty rather than failing', () => {
    expect(srcs({ relation: 'after', edge_image: null })).toEqual([
      null,
      candidateCrop,
      '+2 min',
    ])
  })
})

describe('merge candidate labels', () => {
  test('when reads as a direction in time', () => {
    expect(getWhenLabel('before', -240)).toBe('4 min earlier')
    expect(getWhenLabel('after', 20)).toBe('20 s later')
    expect(getWhenLabel('after', 3900)).toBe('1 h 5 min later')
    expect(getWhenLabel('overlapping', 0)).toBe('Overlaps')
  })

  test('distance and similarity are percentages, or n/a without a value', () => {
    expect(getDistanceLabel(0.0123)).toBe('1.2%')
    expect(getDistanceLabel(null)).toBe('n/a')
    expect(getSimilarityLabel(0.987)).toBe('99%')
    expect(getSimilarityLabel(null)).toBe('n/a')
  })
})

describe('merge candidate sorting', () => {
  const rows: MergeCandidate[] = [
    serverCandidate({ id: 1, time_offset_seconds: 60, similarity: null }),
    serverCandidate({
      id: 2,
      relation: 'before',
      time_offset_seconds: -30,
      distance: 0.5,
      similarity: 0.7,
    }),
    serverCandidate({
      id: 3,
      relation: 'overlapping',
      time_offset_seconds: 0,
      distance: null,
      similarity: 0.9,
    }),
  ].map(convertMergeCandidate)

  const ids = (sorted: MergeCandidate[]) => sorted.map((row) => row.id)

  test('no sort keeps the order the server ranked by cost', () => {
    expect(ids(sortMergeCandidates(rows))).toEqual(['1', '2', '3'])
  })

  test('when runs earliest first and flips when descending', () => {
    expect(
      ids(sortMergeCandidates(rows, { column: 'when', descending: false }))
    ).toEqual(['2', '3', '1'])
    expect(
      ids(sortMergeCandidates(rows, { column: 'when', descending: true }))
    ).toEqual(['1', '3', '2'])
  })

  test('rows without a value go last in either direction', () => {
    expect(
      ids(sortMergeCandidates(rows, { column: 'distance', descending: false }))
    ).toEqual(['1', '2', '3'])
    expect(
      ids(sortMergeCandidates(rows, { column: 'distance', descending: true }))
    ).toEqual(['2', '1', '3'])
    expect(
      ids(sortMergeCandidates(rows, { column: 'similarity', descending: true }))
    ).toEqual(['3', '2', '1'])
  })
})
