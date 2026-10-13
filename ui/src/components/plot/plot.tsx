import classNames from 'classnames'
import _ from 'lodash'
import { CONSTANTS } from 'nova-ui-kit/constants'
import _Plot from 'react-plotly.js'
import styles from './plot.module.scss'
import { PlotProps } from './types'

const fontFamily = 'Mazzard, sans-serif'
const borderColor = CONSTANTS.COLOR_THEME.border
const markerColor = CONSTANTS.COLORS.secondary[500]
const textColor = CONSTANTS.COLOR_THEME.foreground
const titleColor = CONSTANTS.COLOR_THEME.muted.foreground
const tooltipBgColor = CONSTANTS.COLORS.generic.white
const tooltipBorderColor = CONSTANTS.COLOR_THEME.muted.foreground

const Plot = ({
  title,
  data,
  orientation,
  type = 'bar',
  showRangeSlider,
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
          hovertemplate:
            type === 'bar' && orientation === 'h'
              ? '%{x}'
              : type === 'bar'
              ? '%{y}'
              : '<b>%{x}</b>: %{y}',
          name: '', // Remove ‘trace 0’ next to hover
        },
      ]}
      config={{
        autosizable: false,
        modeBarButtons: [['toImage']],
        toImageButtonOptions: {
          filename: _.snakeCase(title),
          scale: 4,
        },
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
          fixedrange: true,
          showgrid: true,
          gridcolor: borderColor,
          zeroline: true,
          zerolinecolor: borderColor,
          automargin: true,
        },
        xaxis: {
          color: textColor,
          fixedrange: type !== 'scatter', // Make zoom available for scatter plots
          showgrid: false,
          zeroline: false,
          tickvals: data.tickvals,
          ticktext: data.ticktext,
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
