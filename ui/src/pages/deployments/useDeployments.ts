import { Deployment } from './types'

export const useDeployments = (): Deployment[] => {
  // TODO: Use real data

  return [
    {
      name: 'Newfoundland-Warren',
      numDetections: 23,
      numEvents: 1,
      numSourceImages: 1557,
    },
    {
      name: 'Panama',
      numDetections: 63,
      numEvents: 1,
      numSourceImages: 3,
    },
    {
      name: 'Vermont-Snapshots-Sample',
      numDetections: 172,
      numEvents: 5,
      numSourceImages: 178,
    },
  ]
}
