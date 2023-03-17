import { STRING, translate } from 'utils/language'
import { BatchData, BatchStatus } from './types'

const batchStatusLabels: { [key in BatchStatus]: string } = {
  [BatchStatus.Running]: translate(STRING.RUNNING),
  [BatchStatus.Stopped]: translate(STRING.STOPPED),
}

const batchData: BatchData[] = [
  {
    complete: 19,
    description: 'Unprocessed images',
    id: 'unprocessed',
    queued: 0,
    status: BatchStatus.Stopped,
    statusLabel: batchStatusLabels[BatchStatus.Stopped],
    unprocessed: 159,
  },
  {
    complete: 166,
    description: 'Detected objects',
    id: 'detected',
    queued: 0,
    status: BatchStatus.Stopped,
    statusLabel: batchStatusLabels[BatchStatus.Stopped],
    unprocessed: 0,
  },
  {
    complete: 148,
    description: 'Unclassified objects',
    id: 'unclassified',
    queued: 0,
    status: BatchStatus.Stopped,
    statusLabel: batchStatusLabels[BatchStatus.Stopped],
    unprocessed: 0,
  },
  {
    complete: 148,
    description: 'Detections without features',
    id: 'without-features',
    queued: 0,
    status: BatchStatus.Stopped,
    statusLabel: batchStatusLabels[BatchStatus.Stopped],
    unprocessed: 0,
  },
  {
    complete: 148,
    description: 'Untracked detections',
    id: 'untracked',
    queued: 0,
    status: BatchStatus.Stopped,
    statusLabel: batchStatusLabels[BatchStatus.Stopped],
    unprocessed: 0,
  },
]

export const useBatchData = (): BatchData[] => {
  // TODO: Use real data

  return batchData
}
