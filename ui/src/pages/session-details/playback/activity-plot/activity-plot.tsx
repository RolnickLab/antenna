import { SessionDetails } from 'data-services/models/session-details'
import { TimelineTick } from 'data-services/models/timeline-tick'
import { useRef } from 'react'
import Plot from 'react-plotly.js'
import { useDynamicPlotWidth } from './useDynamicPlotWidth'

const fontFamily = 'AzoSans, sans-serif'
const lineColorCaptures = '#4e5051'
const lineColorDetections = '#5f8ac6'
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
              mode: 'lines',
              line: { color: lineColorCaptures, width: 1 },
              name: 'Captures',
              yaxis: 'y', // This refers to the first `yaxis` property
            },
            {
              x: timeline.map((timelineTick) => timelineTick.startDate),
              y: timeline.map((timelineTick) => timelineTick.avgDetections),
              text: timeline.map((timelineTick) => timelineTick.tooltip),
              hovertemplate: '%{text}<extra></extra>',
              fill: 'tozeroy',
              type: 'scatter',
              mode: 'lines',
              line: { color: lineColorDetections, width: 1 },
              name: 'Avg. Detections',
              yaxis: 'y2', // This refers to the `yaxis2` property
            },
          ]}
          layout={{
            height: 100,
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
              // y-axis for captures
              showgrid: false,
              showticklabels: false,
              zeroline: false,
              rangemode: 'nonnegative',
              fixedrange: true,
              side: 'left',
            },
            yaxis2: {
              // y-axis for detections
              showgrid: false,
              showticklabels: false,
              zeroline: false,
              rangemode: 'nonnegative',
              fixedrange: true,
              range: [0, session.detectionsMaxCount],
              side: 'right',
              overlaying: 'y',
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
            if (timelineTick?.representativeCaptureId) {
              setActiveCaptureId(timelineTick.representativeCaptureId)
            }
          }}
        />
      </div>
    </div>
  )
}
