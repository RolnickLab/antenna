import { mapServerErrors } from '../map-server-errors'

const known = {
  configFields: ['taxa_list_id', 'reweight'],
}

describe('mapServerErrors', () => {
  test('maps "<field>: message" config errors onto generated fields', () => {
    const { fieldErrors, general } = mapServerErrors(
      {
        params: {
          config: [
            'taxa_list_id: field required',
            'reweight: value could not be parsed to a boolean',
          ],
        },
      },
      known
    )
    expect(fieldErrors).toEqual({
      'config.taxa_list_id': 'field required',
      'config.reweight': 'value could not be parsed to a boolean',
    })
    expect(general).toEqual([])
  })

  test('leaves messages that match no field general', () => {
    const { fieldErrors, general } = mapServerErrors(
      {
        params: { task: 'Unknown task', config: ['other: bad'] },
        detail: 'Nope',
      },
      known
    )
    expect(fieldErrors).toEqual({})
    expect(general).toEqual(['Unknown task', 'other: bad', 'Nope'])
  })
})
