import { getCompactDatespanString } from 'utils/getCompactDatespanString'
import { getCompactTimespanString } from 'utils/getCompactTimespanString'
import events from './example-data/events.json'
import { Session } from './types'

export const useSessions = (): Session[] => {
  // TODO: Use real data

  return events.map((event, index) => {
    return {
      avgTemp: '[WIP] Avg temp',
      datespan: getCompactDatespanString({
        date1: new Date(event.start_time),
        date2: new Date(event.end_time),
      }),
      deployment: event.deployment,
      durationLabel: event.duration_label,
      durationMinutes: event.duration_minutes,
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
      numDetections: event.num_detections,
      numImages: event.num_source_images,
      numOccurrences: 0, // WIP
      numSpecies: 0, // WIP
      timespan: getCompactTimespanString({
        date1: new Date(event.start_time),
        date2: new Date(event.end_time),
      }),
      timestamp: new Date(event.start_time),
    }
  })
}
