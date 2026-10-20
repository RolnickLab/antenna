// The models import the UI kit, whose stylesheets jest cannot load.
jest.mock('nova-ui-kit', () => ({}))

import { Export } from './export'

describe('Export.filtersLabels', () => {
  test('names a related filter, such as an occurrence set', () => {
    const item = new Export({
      id: 1,
      filters: { occurrence_set_id: 7 },
      filters_display: { occurrence_set: { id: 7, name: 'Evaluation set' } },
    })

    expect(item.filtersLabels).toEqual(['Occurrence set: Evaluation set'])
  })

  test('falls back to the raw filters when there is no display version', () => {
    const item = new Export({ id: 1, filters: { collection_id: 3 } })

    expect(item.filtersLabels).toEqual(['Capture set id: 3'])
  })
})
