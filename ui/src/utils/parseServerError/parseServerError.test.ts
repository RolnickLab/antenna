import { parseServerError } from './parseServerError'

describe('parseServerError', () => {
  test('returns a genric error message and a list of field errors', () => {
    const EXAMPLE_ERROR = {
      message: 'Please provide valid values.',
      response: {
        data: {
          email: ['Please provide a valid email.'],
          password: ['Please provide a valid password.'],
        },
      },
    }

    expect(parseServerError(EXAMPLE_ERROR)).toEqual({
      message: 'Please provide valid values.',
      fieldErrors: [
        { key: 'email', message: 'Please provide a valid email.' },
        { key: 'password', message: 'Please provide a valid password.' },
      ],
    })
  })

  test('returns max one message per field', () => {
    const EXAMPLE_ERROR = {
      response: {
        data: {
          password: [
            'The password must contain at least 8 characters.',
            'The password and cannot be entirely numeric.',
          ],
        },
      },
    }

    const { fieldErrors } = parseServerError(EXAMPLE_ERROR)

    expect(fieldErrors).toEqual([
      {
        key: 'password',
        message: 'The password must contain at least 8 characters.',
      },
    ])
  })

  test('will handle special keys in response data as messages, rather than field errors', () => {
    const EXAMPLE_ERROR_1 = {
      response: {
        data: {
          non_field_errors: 'Could not update the user.',
        },
      },
    }

    const EXAMPLE_ERROR_2 = {
      response: {
        data: {
          detail: 'Authentication credentials were not provided.',
        },
      },
    }

    const error1 = parseServerError(EXAMPLE_ERROR_1)
    const error2 = parseServerError(EXAMPLE_ERROR_2)

    expect(error1).toEqual({
      message: 'Could not update the user.',
      fieldErrors: [],
    })
    expect(error2).toEqual({
      message: 'Authentication credentials were not provided.',
      fieldErrors: [],
    })
  })

  test('returns a default error if no information is present', () => {
    const { message, fieldErrors } = parseServerError({})

    expect(message).toEqual('Something went wrong.')
    expect(fieldErrors).toEqual([])
  })

  test('ignores response formats that are not recognized', () => {
    const { fieldErrors: fieldErrors1 } = parseServerError({
      response: '',
    })

    const { fieldErrors: fieldErrors2 } = parseServerError({
      response: {
        data: '',
      },
    })

    const { fieldErrors: fieldErrors3 } = parseServerError({
      response: {
        data: [''],
      },
    })

    expect(fieldErrors1).toEqual([])
    expect(fieldErrors2).toEqual([])
    expect(fieldErrors3).toEqual([])
  })
})
