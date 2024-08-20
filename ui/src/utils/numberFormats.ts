export const bytesToMB = (bytes: number) => bytes / (1024 * 1024)

export const getTotalLabel = (
  sample_length: number,
  known_total: number | undefined
) => {
  // If the known total provided and is more than the sample length, show the sample length followed by a '+'
  return known_total
    ? `${sample_length}${sample_length < known_total ? '+' : ''}`
    : sample_length
}
