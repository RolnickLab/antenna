// Help functions to handle boolean filters (search param values are defined as strings and need to be converted)
export const stringToBoolean = (string?: string) => {
  switch (string?.toLowerCase()) {
    case 'true':
    case '1':
      return true
    case 'false':
    case '0':
      return false
    default:
      return undefined
  }
}

export const booleanToString = (value?: boolean) =>
  value !== undefined ? `${value}` : ''
