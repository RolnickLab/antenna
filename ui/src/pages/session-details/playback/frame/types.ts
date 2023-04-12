export interface FrameDetection {
  id: number
  bbox: number[]
  label: string | null
}

export interface BoxStyle {
  width: string
  height: string
  top: string
  left: string
}
