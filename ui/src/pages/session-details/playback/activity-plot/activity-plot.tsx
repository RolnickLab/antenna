import { useRef } from 'react'
import Plot from 'react-plotly.js'
import { getCompactTimespanString } from 'utils/date/getCompactTimespanString/getCompactTimespanString'
import { findClosestCaptureId } from '../utils'
import { ActivityPlotProps } from './types'
import { useDynamicPlotWidth } from './useDynamicPlotWidth'

const fontFamily = 'Mazzard, sans-serif'
const lineColorCaptures = '#4E4F57'
const lineColorDetections = '#5F8AC6'
const lineColorProcessed = '#FF0000'
const spikeColor = '#FFFFFF'
const textColor = '#303137'
const tooltipBgColor = '#FFFFFF'
const tooltipBorderColor = '#303137'

const ActivityPlot = ({
  session,
  snapToDetections,
  timeline,
  setActiveCaptureId,
}: ActivityPlotProps) => {
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
              hovertemplate: 'Captures: %{y}<extra></extra>',
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
              hovertemplate: 'Avg. detections: %{y}<extra></extra>',
              fill: 'tozeroy',
              type: 'scatter',
              mode: 'lines',
              line: { color: lineColorDetections, width: 1 },
              name: 'Avg. detections',
              yaxis: 'y2',
            },
            {
              x: timeline.map(
                (timelineTick) => new Date(timelineTick.startDate)
              ),
              y: timeline.map((timelineTick) =>
                timelineTick.numCaptures > 0
                  ? timelineTick.wasProcessed
                    ? 0
                    : 1
                  : 0
              ),
              customdata: timeline.map((timelineTick) =>
                timelineTick.numCaptures > 0
                  ? timelineTick.wasProcessed
                    ? 'Yes'
                    : 'No'
                  : 'N/A'
              ),
              hovertemplate: 'Was processed: %{customdata}<extra></extra>',
              fill: 'tozeroy',
              type: 'scatter',
              mode: 'lines',
              line: { color: lineColorProcessed, width: 1 },
              name: 'Was processed',
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
            hovermode: 'x unified',
            // y-axis for captures
            yaxis: {
              showgrid: false,
              showticklabels: false,
              zeroline: false,
              rangemode: 'nonnegative',
              fixedrange: true,
              range: [yAxisMin, yAxisMax],
              side: 'left',
            },
            // y-axis for detections
            yaxis2: {
              showgrid: false,
              showticklabels: false,
              zeroline: false,
              rangemode: 'nonnegative',
              fixedrange: true,
              range: [0, Math.max(session.detectionsMaxCount ?? 0, 1)], // Ensure a minimum range of 1
              side: 'right',
              overlaying: 'y',
            },
            xaxis: {
              fixedrange: true,
              range: [new Date(session.startDate), new Date(session.endDate)],
              showgrid: false,
              showline: false,
              showticklabels: false,
              spikecolor: spikeColor,
              spikethickness: -2,
              ticktext: timeline.map((timelineTick) =>
                getCompactTimespanString({
                  date1: timelineTick.startDate,
                  date2: timelineTick.endDate,
                  options: {
                    second: true,
                  },
                })
              ),
              tickvals: timeline.map(
                (timelineTick) => new Date(timelineTick.startDate)
              ),
              zeroline: false,
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

            if (!timelineTick) {
              return
            }

            const captureId =
              snapToDetections || !timelineTick.representativeCaptureId
                ? findClosestCaptureId({
                    snapToDetections,
                    timeline,
                    targetDate: timelineTick.startDate,
                  })
                : timelineTick.representativeCaptureId

            if (captureId) {
              setActiveCaptureId(captureId)
            }
          }}
        />
      </div>
    </div>
  )
}

export default ActivityPlot
