import { getFormErrors } from './form-errors'

const badRequest = (data: unknown) => ({
  message: 'Request failed with status code 400',
  response: { data },
})

describe('getFormErrors', () => {
  test('puts a name error on the name field, with no banner', () => {
    expect(
      getFormErrors(badRequest({ name: ['This field may not be blank.'] }))
    ).toEqual({
      nameError: 'This field may not be blank.',
      formError: undefined,
    })
  })

  test('shows errors on fields the form does not have in the banner', () => {
    expect(
      getFormErrors(
        badRequest({
          occurrence_ids: ['Not occurrences in project 1: [999999]'],
        })
      )
    ).toEqual({
      nameError: undefined,
      formError: 'Not occurrences in project 1: [999999]',
    })
  })

  test('shows a detail message in the banner', () => {
    expect(
      getFormErrors({
        message: 'Request failed with status code 403',
        response: { data: { detail: 'Permission denied.' } },
      })
    ).toEqual({ nameError: undefined, formError: 'Permission denied.' })
  })

  test('returns nothing without an error', () => {
    expect(getFormErrors(null)).toEqual({})
  })
})
