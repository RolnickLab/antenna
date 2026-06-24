import { render } from '@testing-library/react'
import React from 'react'
import { SiteFilter } from './site-filter'

// Capture the props that EntityPicker receives so we can assert on them.
let capturedEntityPickerProps: Record<string, unknown> = {}

jest.mock('nova-ui-kit', () => ({
  EntityPicker: (props: Record<string, unknown>) => {
    capturedEntityPickerProps = props
    return null
  },
}))

jest.mock('data-services/constants', () => ({
  API_ROUTES: {
    SITES: 'deployments/sites',
  },
}))

describe('SiteFilter', () => {
  beforeEach(() => {
    capturedEntityPickerProps = {}
  })

  test('passes API_ROUTES.SITES as the collection prop to EntityPicker', () => {
    const onAdd = jest.fn()
    const onClear = jest.fn()

    render(<SiteFilter onAdd={onAdd} onClear={onClear} value={undefined} />)

    expect(capturedEntityPickerProps.collection).toBe('deployments/sites')
  })

  test('passes the current value to EntityPicker', () => {
    const onAdd = jest.fn()
    const onClear = jest.fn()

    render(<SiteFilter onAdd={onAdd} onClear={onClear} value="99" />)

    expect(capturedEntityPickerProps.value).toBe('99')
  })

  test('passes undefined value to EntityPicker when no value is set', () => {
    const onAdd = jest.fn()
    const onClear = jest.fn()

    render(<SiteFilter onAdd={onAdd} onClear={onClear} value={undefined} />)

    expect(capturedEntityPickerProps.value).toBeUndefined()
  })

  test('calls onAdd with the selected value when EntityPicker fires a truthy value', () => {
    const onAdd = jest.fn()
    const onClear = jest.fn()

    render(<SiteFilter onAdd={onAdd} onClear={onClear} value={undefined} />)

    const onValueChange = capturedEntityPickerProps.onValueChange as (
      v: string | undefined
    ) => void
    onValueChange('99')

    expect(onAdd).toHaveBeenCalledTimes(1)
    expect(onAdd).toHaveBeenCalledWith('99')
    expect(onClear).not.toHaveBeenCalled()
  })

  test('calls onClear when EntityPicker fires an empty string', () => {
    const onAdd = jest.fn()
    const onClear = jest.fn()

    render(<SiteFilter onAdd={onAdd} onClear={onClear} value="99" />)

    const onValueChange = capturedEntityPickerProps.onValueChange as (
      v: string | undefined
    ) => void
    onValueChange('')

    expect(onClear).toHaveBeenCalledTimes(1)
    expect(onAdd).not.toHaveBeenCalled()
  })

  test('calls onClear when EntityPicker fires undefined', () => {
    const onAdd = jest.fn()
    const onClear = jest.fn()

    render(<SiteFilter onAdd={onAdd} onClear={onClear} value="99" />)

    const onValueChange = capturedEntityPickerProps.onValueChange as (
      v: string | undefined
    ) => void
    onValueChange(undefined)

    expect(onClear).toHaveBeenCalledTimes(1)
    expect(onAdd).not.toHaveBeenCalled()
  })
})