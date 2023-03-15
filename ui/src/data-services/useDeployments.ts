import deployments from './example-data/deployments.json'
import { Deployment } from './types'

export const useDeployments = (): Deployment[] => {
  // TODO: Use real data

  return deployments.map((deployment, index) => ({
    id: `#${index}`,
    name: deployment.name,
    numDetections: deployment.num_detections,
    numEvents: deployment.num_events,
    numSourceImages: deployment.num_source_images,
  }))
}
