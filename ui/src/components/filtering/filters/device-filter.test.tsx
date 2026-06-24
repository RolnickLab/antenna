import { render } from '@testing-library/react'
import React from 'react'
import { DeviceFilter } from './device-filter'

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
    DEVICES: 'deployments/devices',
  },
}))

describe('DeviceFilter', () => {
  beforeEach(() => {
    capturedEntityPickerProps = {}
  })

  test('passes API_ROUTES.DEVICES as the collection prop to EntityPicker', () => {
    const onAdd = jest.fn()
    const onClear = jest.fn()

    render(<DeviceFilter onAdd={onAdd} onClear={onClear} value={undefined} />)

    expect(capturedEntityPickerProps.collection).toBe('deployments/devices')
  })

  test('passes the current value to EntityPicker', () => {
    const onAdd = jest.fn()
    const onClear = jest.fn()

    render(<DeviceFilter onAdd={onAdd} onClear={onClear} value="42" />)

    expect(capturedEntityPickerProps.value).toBe('42')
  })

  test('passes undefined value to EntityPicker when no value is set', () => {
    const onAdd = jest.fn()
    const onClear = jest.fn()

    render(<DeviceFilter onAdd={onAdd} onClear={onClear} value={undefined} />)

    expect(capturedEntityPickerProps.value).toBeUndefined()
  })

  test('calls onAdd with the selected value when EntityPicker fires a truthy value', () => {
    const onAdd = jest.fn()
    const onClear = jest.fn()

    render(<DeviceFilter onAdd={onAdd} onClear={onClear} value={undefined} />)

    const onValueChange = capturedEntityPickerProps.onValueChange as (
      v: string | undefined
    ) => void
    onValueChange('42')

    expect(onAdd).toHaveBeenCalledTimes(1)
    expect(onAdd).toHaveBeenCalledWith('42')
    expect(onClear).not.toHaveBeenCalled()
  })

  test('calls onClear when EntityPicker fires an empty string', () => {
    const onAdd = jest.fn()
    const onClear = jest.fn()

    render(<DeviceFilter onAdd={onAdd} onClear={onClear} value="42" />)

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

    render(<DeviceFilter onAdd={onAdd} onClear={onClear} value="42" />)

    const onValueChange = capturedEntityPickerProps.onValueChange as (
      v: string | undefined
    ) => void
    onValueChange(undefined)

    expect(onClear).toHaveBeenCalledTimes(1)
    expect(onAdd).not.toHaveBeenCalled()
  })
})