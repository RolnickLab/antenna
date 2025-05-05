import { TagData } from './types'

export const AVAILABLE_TAGS: TagData[] = [
  {
    label: 'Unknown species',
    value: 'unknown-species',
  },
  { label: 'Reviewed', value: 'reviewed' },
  { label: 'Most wanted', value: 'most-wanted' },
  { label: 'Also wanted', value: 'also-wanted' },
  { label: 'Found', value: 'found' },
  { label: 'Collected', value: 'collected' },
]

export const TAG_CLASSES: { [key: string]: string | undefined } = {
  'unknown-species': 'bg-success',
}
