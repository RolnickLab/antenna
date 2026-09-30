import { mapServerErrors } from '../map-server-errors'

const known = {
  configFields: ['taxa_list_id', 'reweight'],
  scopeFields: ['source_image_collection_id'],
}

describe('mapServerErrors', () => {
  test('maps "<field>: message" config errors onto generated fields', () => {
    const { fieldErrors, general } = mapServerErrors(
      {
        params: {
          config: [
            'taxa_list_id: field required',
            'reweight: Only staff can change this setting.',
          ],
        },
      },
      known
    )
    expect(fieldErrors).toEqual({
      'config.taxa_list_id': 'field required',
      'config.reweight': 'Only staff can change this setting.',
    })
    expect(general).toEqual([])
  })

  test('maps scope errors and leaves unmatched messages general', () => {
    const { fieldErrors, general } = mapServerErrors(
      {
        source_image_collection_id: ['Not found in this project.'],
        params: { task: 'Unknown task', config: ['other: bad'] },
        detail: 'Nope',
      },
      known
    )
    expect(fieldErrors).toEqual({
      'scope.source_image_collection_id': 'Not found in this project.',
    })
    expect(general).toEqual(['Unknown task', 'other: bad', 'Nope'])
  })
})
