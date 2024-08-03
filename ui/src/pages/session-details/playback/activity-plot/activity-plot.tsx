import { SessionDetails } from 'data-services/models/session-details'
import { TimelineTick } from 'data-services/models/timeline-tick'
import { useRef } from 'react'
import Plot from 'react-plotly.js'
import { useDynamicPlotWidth } from './useDynamicPlotWidth'
const fontFamily = 'AzoSans, sans-serif'
const lineColorDetections = '#5f8ac6'
const lineColorCaptures = '#4CAF50'
const textColor = '#222426'
const tooltipBgColor = '#ffffff'
const tooltipBorderColor = '#222426'
export const ActivityPlot = ({
  session,
  timeline,
  setActiveCaptureId,
}: {
  session: SessionDetails
  timeline: TimelineTick[]
  setActiveCaptureId: (captureId: string) => void
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
              x: timeline.map((timelineTick) => timelineTick.startDate),
              y: timeline.map((timelineTick) => timelineTick.numCaptures),
              text: timeline.map((timelineTick) => timelineTick.tooltip),
              hovertemplate: '%{text}<extra></extra>',
              fill: 'tozeroy',
              type: 'scatter',
              mode: 'lines+markers',
              line: { color: lineColorCaptures, width: 1 },
              name: 'Captures',
            },
            {
              x: timeline.map((timelineTick) => timelineTick.startDate),
              y: timeline.map((timelineTick) => timelineTick.numDetections),
              text: timeline.map((timelineTick) => timelineTick.tooltip),
              hovertemplate: '%{text}<extra></extra>',
              fill: 'tozeroy',
              type: 'scatter',
              mode: 'lines',
              line: { color: lineColorDetections, width: 1 },
              name: 'Detections',
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
              range: [session.startDate, session.endDate],
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
            showlegend: false,
          }}
          config={{
            displayModeBar: false,
          }}
          onClick={(data) => {
            const timelineTickIndex = data.points[0].pointIndex
            const timelineTick = timeline[timelineTickIndex]
            if (timelineTick?.firstCaptureId) {
              setActiveCaptureId(timelineTick.firstCaptureId)
            }
          }}
        />
      </div>
    </div>
  )
}
