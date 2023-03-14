import { getCompactTimespanString } from 'utils/getCompactTimespanString'
import detections from './example-data/detections.json'
import events from './example-data/events.json'
import { Occurrence } from './types'

export const useOccurrences = (): Occurrence[] => {
  // TODO: Use real data

  return detections.map((detection) => {
    const event = events.find((e) => e.event === detection.event)

    return {
      appearanceDuration: '[WIP] Appearance duration',
      appearanceTimespan: '[WIP] Appearance timespan',
      categoryLabel: detection.category_label,
      deployment: detection.deployment,
      deploymentLocation: '[WIP] Deployment location',
      familyLabel: '[WIP] Family',
      sessionId: '[WIP] Session ID',
      sessionTimespan: event
        ? getCompactTimespanString({
            date1: new Date(event.start_time),
            date2: new Date(event.end_time),
          })
        : '',
    }
  })
}
