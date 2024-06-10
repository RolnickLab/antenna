/**
 * Offsets the thumb centre point to ensure it remains within the bounds of the slider when reaching the edges.
 *
 * https://github.com/radix-ui/primitives/blob/main/packages/react/slider/src/Slider.tsx
 */
export const getThumbInBoundsOffset = (thumbWidth: number, value: number) => {
  const halfWidth = thumbWidth / 2
  const halfPercent = 50
  const offset = linearScale([0, halfPercent], [0, halfWidth])
  return halfWidth - offset(value)
}

const linearScale = (input: [number, number], output: [number, number]) => {
  return (value: number) => {
    if (input[0] === input[1] || output[0] === output[1]) {
      return output[0]
    }
    const ratio = (output[1] - output[0]) / (input[1] - input[0])
    return output[0] + ratio * (value - input[0])
  }
}
