import _Plot from 'react-plotly.js'
import styles from './plot.module.scss'

const fontFamily = 'AzoSans, sans-serif'
const borderColor = '#f0f0f0'
const markerColor = '#5f8ac6'
const textColor = '#222426'
const titleColor = '#6f7172'
const tooltipBgColor = '#ffffff'
const tooltipBorderColor = '#222426'

interface PlotProps {
  title: string
  data: {
    x: (string | number)[]
    y: (string | number)[]
    tickvals?: (string | number)[]
    ticktext?: string[]
  }
  type?: 'bar' | 'scatter'
  showRangeSlider?: boolean
}

export const Plot = ({
  title,
  data,
  type = 'bar',
  showRangeSlider,
}: PlotProps) => (
  <div className={styles.plot}>
    <_Plot
      data={[
        {
          type: type,
          x: data.x,
          y: data.y,
          marker: {
            color: markerColor,
          },
        },
      ]}
      config={{
        displayModeBar: false,
        autosizable: false,
      }}
      layout={{
        title: {
          x: 0,
          text: title,
          font: {
            family: fontFamily,
            size: 14,
            color: titleColor,
          },
        },
        width: 320,
        height: 240,
        paper_bgcolor: 'transparent',
        plot_bgcolor: 'transparent',
        font: {
          family: fontFamily,
          size: 12,
          color: textColor,
        },
        margin: {
          l: 32,
          r: 0,
          b: 32,
          t: 32,
          pad: 8,
        },
        yaxis: {
          color: textColor,
          showgrid: true,
          gridcolor: borderColor,
          zeroline: true,
          zerolinecolor: borderColor,
        },
        xaxis: {
          color: textColor,
          showgrid: false,
          zeroline: false,
          type: 'category',
          tickvals: data.tickvals,
          ticktext: data.ticktext,
          ...(showRangeSlider
            ? {
                range: [0, 3],
                rangeslider: {
                  visible: true,
                },
              }
            : {}),
        },
        bargap: 2 / 3,
        hoverlabel: {
          bgcolor: tooltipBgColor,
          bordercolor: tooltipBorderColor,
          font: {
            family: fontFamily,
            size: 12,
            color: textColor,
          },
        },
        autosize: false,
      }}
    />
  </div>
)
