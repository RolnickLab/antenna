import _ from 'lodash'
import { getCompactDatespanString } from 'utils/getCompactDatespanString'
import detections from './example-data/detections.json'
import events from './example-data/events.json'
import { Occurrence } from './types'

export const useOccurrences = (): Occurrence[] => {
  // TODO: Use real data

  return detections.map((detection, index) => {
    const event = events.find((e) => e.event === detection.event)

    return {
      appearanceDuration: '[WIP] Appearance duration',
      appearanceTimespan: '[WIP] Appearance timespan',
      categoryLabel: detection.category_label,
      categoryScore: _.round(detection.category_score, 2),
      deployment: detection.deployment,
      deploymentLocation: '[WIP] Deployment location',
      familyLabel: '[WIP] Family',
      id: `[WIP] #${index}`,
      images: [
        {
          src: 'https://placekitten.com/240/240',
        },
        {
          src: 'https://placekitten.com/240/160',
        },
        {
          src: 'https://placekitten.com/160/240',
        },
      ],
      sessionId: '[WIP] Session ID',
      sessionTimespan: event
        ? getCompactDatespanString({
            date1: new Date(event.start_time),
            date2: new Date(event.end_time),
          })
        : '',
      timestamp: new Date(detection.timestamp),
    }
  })
}
