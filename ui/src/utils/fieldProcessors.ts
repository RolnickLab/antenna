// Utility functions for processing form field values
import { STRING, translate } from './language'

/**
 * Validate that a value is an integer with translated error message
 * @param value - Value to validate
 * @returns undefined if valid, translated error message if invalid
 */
export const validateInteger = (value: any): string | undefined => {
  if (value) {
    if (!Number.isInteger(Number(value))) {
      return translate(STRING.MESSAGE_VALUE_INVALID)
    }
  }
  return undefined
}

/**
 * Convert comma-separated string to integer array
 * @param value - Comma-separated string (e.g., "1, 2, 3")
 * @returns Array of integers or null if empty
 */
export const parseIntegerList = (
  value: string | undefined
): number[] | null => {
  if (!value || value.trim() === '') return null
  const ids = value
    .split(',')
    .map((id) => parseInt(id.trim(), 10))
    .filter((id) => !isNaN(id))
  return ids.length > 0 ? ids : null
}

/**
 * Convert integer array to comma-separated string
 * @param value - Array of integers
 * @returns Comma-separated string for display in form
 */
export const formatIntegerList = (
  value: number[] | null | undefined
): string => {
  if (!value || !Array.isArray(value) || value.length === 0) return ''
  return value.join(', ')
}

/**
 * Validate comma-separated integer list input
 * @param value - Input string to validate
 * @returns undefined if valid, error message if invalid
 */
export const validateIntegerList = (
  value: string | undefined
): string | undefined => {
  if (!value || value.trim() === '') return undefined // Optional field
  const pattern = /^\s*\d+\s*(?:\s*,\s*\d+\s*)*$/
  if (!pattern.test(value)) {
    return 'Enter comma-separated integers (e.g., 1, 2, 3).'
  }
  return undefined
}
