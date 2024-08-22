import { bytesToMB, getTotalLabel } from '.'

describe('bytesToMB', () => {
  test('will convert bytes to MB', () => {
    const sizeBytes = 1024 * 1024 * 30
    const sizeMB = 30
    const result = bytesToMB(sizeBytes)
    expect(result).toEqual(sizeMB)
  })
})

describe('getTotalLabel', () => {
  test(`will show the sample length followed by a '+' if the known total is more than the sample length`, () => {
    const result = getTotalLabel(10, 100)
    expect(result).toEqual('10+')
  })

  test('will show the sample length if the known total is equal to the sample length', () => {
    const result = getTotalLabel(10, 10)
    expect(result).toEqual('10')
  })
})
