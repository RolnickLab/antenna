import { missingCropSize } from './crop-size'

describe('missingCropSize', () => {
  test('a wide box fills the column width and keeps its proportions', () => {
    expect(missingCropSize(300, 100)).toEqual({ width: 96, height: 32 })
  })

  test('a tall box is capped by the column height instead', () => {
    expect(missingCropSize(100, 300)).toEqual({ width: 40, height: 120 })
  })

  test('unknown proportions give a square filling the column', () => {
    expect(missingCropSize(0, 0)).toEqual({ width: 96, height: 96 })
    expect(missingCropSize(NaN, -5)).toEqual({ width: 96, height: 96 })
  })
})
