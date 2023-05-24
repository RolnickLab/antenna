export const isEmpty = (value?: any) =>
  value == null || (typeof value === 'string' && value.trim().length === 0)
