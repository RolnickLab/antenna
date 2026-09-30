// Server validation errors arrive as DRF JSON. Config problems are strings of
// the form "<field>: message" under params.config; scope problems are keyed by
// the scope field name.
export const mapServerErrors = (
  data: unknown,
  {
    configFields,
    scopeFields,
  }: { configFields: string[]; scopeFields: string[] }
) => {
  const fieldErrors: { [formName: string]: string } = {}
  const general: string[] = []

  const asList = (value: unknown): string[] =>
    (Array.isArray(value) ? value : [value])
      .filter((item) => item !== undefined && item !== null)
      .map((item) => (typeof item === 'string' ? item : JSON.stringify(item)))

  if (!data || typeof data !== 'object') {
    return { fieldErrors, general }
  }

  Object.entries(data as { [key: string]: unknown }).forEach(([key, value]) => {
    if (key === 'params' && value && typeof value === 'object') {
      Object.entries(value as { [key: string]: unknown }).forEach(
        ([paramKey, paramValue]) => {
          asList(paramValue).forEach((message) => {
            const separator = message.indexOf(': ')
            const field = separator > 0 ? message.slice(0, separator) : ''
            if (paramKey === 'config' && configFields.includes(field)) {
              fieldErrors[`config.${field}`] ??= message.slice(separator + 2)
            } else {
              general.push(message)
            }
          })
        }
      )
    } else if (scopeFields.includes(key)) {
      fieldErrors[`scope.${key}`] = asList(value)[0]
    } else {
      general.push(...asList(value))
    }
  })

  return { fieldErrors, general }
}
