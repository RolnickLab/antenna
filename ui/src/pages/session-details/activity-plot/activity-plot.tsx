import { SessionDetails } from 'data-services/models/session-details'
import { TimelineTick } from 'data-services/models/timeline-tick'
import { CONSTANTS } from 'nova-ui-kit'
import { useRef } from 'react'
import Plot from 'react-plotly.js'
import { getCompactTimespanString } from 'utils/date/getCompactTimespanString/getCompactTimespanString'
import { findClosestCaptureId } from '../utils'
import { useDynamicPlotWidth } from './useDynamicPlotWidth'

const fontFamily = 'Mazzard'
const fontSize = 14
const lineColorCaptures = CONSTANTS.COLORS.neutral[300]
const lineColorDetections = CONSTANTS.COLOR_THEME.secondary.DEFAULT
const lineColorTaxon = CONSTANTS.COLOR_THEME.primary.DEFAULT
const spikeColor = CONSTANTS.COLOR_THEME.foreground
const textColor = CONSTANTS.COLOR_THEME.foreground
const tooltipBgColor = CONSTANTS.COLOR_THEME.background
const tooltipBorderColor = CONSTANTS.COLOR_THEME.border

export interface ActivityPlotProps {
  // When set, the detections trace shows this taxon's detections instead of all.
  activeTaxon?: { name: string }
  session: SessionDetails
  setActiveCaptureId: (captureId: string) => void
  timeline: TimelineTick[]
}

export const ActivityPlot = ({
  activeTaxon,
  session,
  timeline,
  setActiveCaptureId,
}: ActivityPlotProps) => {
  const containerRef = useRef(null)
  const width = useDynamicPlotWidth(containerRef)

  const detectionsTrace = activeTaxon
    ? {
        y: timeline.map((timelineTick) => timelineTick.numTaxonDetections),
        hovertemplate: `${activeTaxon.name}: %{y}<extra></extra>`,
        color: lineColorTaxon,
        name: activeTaxon.name,
        max: Math.max(
          ...timeline.map((timelineTick) => timelineTick.numTaxonDetections),
          1
        ),
      }
    : {
        y: timeline.map((timelineTick) => timelineTick.avgDetections),
        hovertemplate: 'Avg. detections: %{y}<extra></extra>',
        color: lineColorDetections,
        name: 'Avg. detections',
        max: Math.max(session.detectionsMaxCount ?? 0, 1), // Ensure a minimum range of 1
      }

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
              y: detectionsTrace.y,
              hovertemplate: detectionsTrace.hovertemplate,
              fill: 'tozeroy',
              type: 'scatter',
              mode: 'lines',
              line: { color: detectionsTrace.color, width: 1 },
              name: detectionsTrace.name,
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
              range: [0, detectionsTrace.max],
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
                size: fontSize,
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

            const captureId = !timelineTick.representativeCaptureId
              ? findClosestCaptureId({
                  snapToDetections: false,
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
