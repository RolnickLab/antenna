export const bytesToMB = (bytes: number) => bytes / (1024 * 1024)

export const getTotalLabel = (
  sampleLength: number,
  knownTotal: number | undefined
) => {
  // If the known total provided and is more than the sample length, show the sample length followed by a '+'
  return knownTotal
    ? `${sampleLength}${sampleLength < knownTotal ? '+' : ''}`
    : sampleLength
}
