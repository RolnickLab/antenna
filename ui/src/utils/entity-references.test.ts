import { linkFor } from './references'

// utils/constants reads import.meta, which ts-jest cannot compile; these mirror its route shapes.
jest.mock('utils/constants', () => ({
  APP_ROUTES: {
    ALGORITHM_DETAILS: (p: { projectId: string; algorithmId: string }) =>
      `/projects/${p.projectId}/algorithms/${p.algorithmId}`,
    CAPTURES: (p: { projectId: string }) => `/projects/${p.projectId}/captures`,
    JOB_DETAILS: (p: { projectId: string; jobId: string }) =>
      `/projects/${p.projectId}/jobs/${p.jobId}`,
    OCCURRENCE_DETAILS: (p: { projectId: string; occurrenceId: string }) =>
      `/projects/${p.projectId}/occurrences/${p.occurrenceId}`,
    TAXA_LIST_DETAILS: (p: { projectId: string; taxaListId: string }) =>
      `/projects/${p.projectId}/taxa-lists/${p.taxaListId}`,
    TAXON_DETAILS: (p: { projectId: string; taxonId: string }) =>
      `/projects/${p.projectId}/taxa/${p.taxonId}`,
  },
}))

describe('linkFor', () => {
  it('links a known type to its page', () => {
    expect(linkFor({ type: 'job', id: 7, name: 'Run' }, '1')).toBe(
      '/projects/1/jobs/7'
    )
    expect(linkFor({ type: 'taxa_list', id: 3, name: 'Kept' }, '1')).toBe(
      '/projects/1/taxa-lists/3'
    )
    expect(linkFor({ type: 'capture_set', id: 5, name: 'Set' }, '1')).toBe(
      '/projects/1/captures?collections=5'
    )
  })

  it('does not link a deleted row or an unknown type', () => {
    expect(linkFor({ type: 'job', id: 7, name: null }, '1')).toBeUndefined()
    expect(
      linkFor({ type: 'something_new', id: 1, name: 'x' }, '1')
    ).toBeUndefined()
  })
})
