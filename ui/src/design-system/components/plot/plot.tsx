import classNames from 'classnames'
import _Plot from 'react-plotly.js'
import styles from './plot.module.scss'
import { PlotProps } from './types'

const fontFamily = 'AzoSans, sans-serif'
const borderColor = '#f0f0f0'
const markerColor = '#5f8ac6'
const textColor = '#222426'
const titleColor = '#6f7172'
const tooltipBgColor = '#ffffff'
const tooltipBorderColor = '#222426'

const Plot = ({
  title,
  data,
  orientation,
  type = 'bar',
  showRangeSlider,
  hovertemplate,
}: PlotProps) => (
  <div
    className={classNames(styles.plot, { [styles.round]: data.x.length >= 3 })}
  >
    <_Plot
      data={[
        {
          orientation,
          type,
          x: data.x,
          y: data.y,
          width:
            orientation === 'h' ? undefined : data.x.length > 3 ? 1 / 3 : 1 / 6,
          marker: {
            color: markerColor,
          },
          hovertemplate: type === 'bar' && orientation === 'h' ? '%{x}' : type === 'bar' ? '%{y}' : '<b>%{x}</b>: %{y}',
          name: "" // Remove ‘trace 0’ next to hover
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
          automargin: true,
        },
        xaxis: {
          color: textColor,
          showgrid: false,
          zeroline: false,
          tickvals: data.tickvals,
          ticktext: data.ticktext,
          tickformat: 'd',
          automargin: true,
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

export default Plot
