export type ChartsSection = {
  id: string
  title: string
  plots: Plot[]
}

export type Plot = {
  title: string
  data: {
    x: (string | number)[]
    y: number[]
    tickvals?: (string | number)[]
    ticktext?: string[]
  }
  orientation: 'h' | 'v'
  type: any
}
