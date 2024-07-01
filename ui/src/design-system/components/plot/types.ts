export interface PlotProps {
  title: string
  orientation?: 'h' | 'v'
  data: {
    x: (string | number)[]
    y: (string | number)[]
    tickvals?: (string | number)[]
    ticktext?: string[]
  }
  type?: 'bar' | 'scatter'
  showRangeSlider?: boolean
  categorical?: boolean
  hovertemplate?: string
}
