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
const gridLineColor = '#f36399'

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

  // Calculate the average number of captures
  const avgCaptures =
    timeline.reduce((sum, tick) => sum + tick.numCaptures, 0) / timeline.length

  // Calculate the maximum deviation from the average
  const maxDeviation = Math.max(
    ...timeline.map((tick) => Math.abs(tick.numCaptures - avgCaptures))
  )

  // Set the y-axis range to be centered around the average
  const yAxisMin = Math.max(0, avgCaptures - maxDeviation)
  const yAxisMax = avgCaptures + maxDeviation

  return (
    <div style={{ margin: '0 14px -10px' }}>
      <div ref={containerRef}>
        <Plot
          style={{ display: 'block' }}
          data={[
            {
              x: timeline.map(
                (timelineTick) => new Date(timelineTick.startDate)
              ),
              y: timeline.map((timelineTick) => timelineTick.numCaptures),
              text: timeline.map((timelineTick) => timelineTick.tooltip),
              hovertemplate: '%{text}<extra></extra>',
              fill: 'tozeroy',
              type: 'scatter',
              mode: 'lines',
              line: { color: lineColorCaptures, width: 1 },
              name: 'Captures',
              yaxis: 'y',
            },
            {
              x: timeline.map(
                (timelineTick) => new Date(timelineTick.startDate)
              ),
              y: timeline.map((timelineTick) => timelineTick.avgDetections),
              text: timeline.map((timelineTick) => timelineTick.tooltip),
              hovertemplate: '%{text}<extra></extra>',
              fill: 'tozeroy',
              type: 'scatter',
              mode: 'lines',
              line: { color: lineColorDetections, width: 1 },
              name: 'Avg. Detections',
              yaxis: 'y2',
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
              showgrid: false,
              showticklabels: false,
              zeroline: false,
              rangemode: 'nonnegative',
              fixedrange: true,
              range: [yAxisMin, yAxisMax],
              side: 'left',
            },
            yaxis2: {
              showgrid: false,
              showticklabels: false,
              zeroline: false,
              rangemode: 'nonnegative',
              fixedrange: true,
              range: [0, session.detectionsMaxCount ?? yAxisMax],
              side: 'right',
              overlaying: 'y',
            },
            xaxis: {
              showline: false,
              showgrid: true,
              griddash: 'dot',
              gridwidth: 1,
              gridcolor: gridLineColor,
              showticklabels: false,
              zeroline: false,
              fixedrange: true,
              range: [new Date(session.startDate), new Date(session.endDate)],
              dtick: 3600000, // milliseconds in an hour
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
