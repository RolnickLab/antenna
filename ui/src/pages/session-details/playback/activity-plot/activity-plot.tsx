import { Capture } from 'data-services/models/capture'
import { useRef } from 'react'
import Plot from 'react-plotly.js'
import { useDynamicPlotWidth } from './useDynamicPlotWidth'

const fontFamily = 'AzoSans, sans-serif'
const lineColor = '#5f8ac6'
const textColor = '#222426'
const tooltipBgColor = '#ffffff'
const tooltipBorderColor = '#222426'

export const ActivityPlot = ({
  captures,
  setActiveCapture,
}: {
  captures: Capture[]
  setActiveCapture: (capture: Capture) => void
}) => {
  const containerRef = useRef(null)
  const width = useDynamicPlotWidth(containerRef)

  return (
    <div style={{ margin: '0 14px -10px' }}>
      <div ref={containerRef}>
        <Plot
          style={{ display: 'block' }}
          data={[
            {
              x: captures.map((capture) => capture.date),
              y: captures.map((capture) => capture.numDetections),
              fill: 'tozeroy',
              type: 'scatter',
              mode: 'lines',
              line: { color: lineColor, width: 1 },
            },
          ]}
          layout={{
            height: 200,
            width: width,
            paper_bgcolor: 'transparent',
            plot_bgcolor: 'transparent',
            margin: {
              l: 0,
              r: 0,
              b: 0,
              t: 0,
              pad: 0,
            },
            yaxis: {
              showgrid: false,
              showticklabels: false,
              zeroline: false,
              rangemode: 'nonnegative',
              fixedrange: true,
            },
            xaxis: {
              showline: true,
              showgrid: false,
              showticklabels: false,
              zeroline: false,
              fixedrange: true,
            },
            hoverlabel: {
              bgcolor: tooltipBgColor,
              bordercolor: tooltipBorderColor,
              font: {
                family: fontFamily,
                size: 12,
                color: textColor,
              },
            },
          }}
          config={{
            displayModeBar: false,
          }}
          onClick={(data) => {
            const captureIndex = data.points[0].pointIndex
            const capture = captures[captureIndex]

            if (capture) {
              setActiveCapture(capture)
            }
          }}
        />
      </div>
    </div>
  )
}
