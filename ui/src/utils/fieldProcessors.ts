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
    return 'Enter comma-separated numbers (e.g., 1, 2, 3).'
  }
  return undefined
}

/**
 * Render a stored metadata object as the JSON text an operator edits.
 *
 * A record with no metadata shows an empty field rather than a bare pair of
 * braces, so the form does not suggest there is something there to read.
 * @param value - Metadata object as returned by the API
 * @returns Indented JSON text, or an empty string when there is no metadata
 */
export const formatMetadata = (value: unknown): string => {
  if (value === null || value === undefined) {
    return ''
  }

  if (typeof value === 'object' && Object.keys(value).length === 0) {
    return ''
  }

  return JSON.stringify(value, null, 2)
}

/**
 * Convert the JSON text from a metadata field into the object the API stores.
 *
 * An empty field means the record has no metadata, which the API represents as
 * an empty object. Validate the text with `validateMetadata` before calling
 * this; text that is not valid JSON raises a parse error.
 * @param value - JSON text from the form field
 * @returns Metadata object to send to the API
 */
export const parseMetadata = (value: string | undefined): object => {
  if (!value || value.trim() === '') {
    return {}
  }

  return JSON.parse(value)
}

/**
 * Check a metadata field while it is being edited, so a typo is reported next
 * to the field instead of coming back as a server error after saving.
 *
 * Metadata has to be a set of names and values. Text that parses as a list, a
 * number or any other JSON value is rejected, because the API stores an object.
 * @param value - JSON text from the form field
 * @returns undefined if valid, error message if invalid
 */
export const validateMetadata = (
  value: string | undefined
): string | undefined => {
  if (!value || value.trim() === '') {
    return undefined // An empty field is allowed and means "no metadata".
  }

  let parsed: unknown

  try {
    parsed = JSON.parse(value)
  } catch {
    return translate(STRING.MESSAGE_METADATA_INVALID)
  }

  if (parsed === null || typeof parsed !== 'object' || Array.isArray(parsed)) {
    return translate(STRING.MESSAGE_METADATA_NOT_OBJECT)
  }

  return undefined
}
