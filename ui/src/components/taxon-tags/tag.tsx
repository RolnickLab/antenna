import classNames from 'classnames'
import { TAG_CLASSES } from './constants'
import { TagData } from './types'

export const Tag = ({ label, value }: TagData) => (
  <div
    className={classNames(
      'h-6 inline-flex items-center px-3 rounded-full bg-primary text-primary-foreground body-small font-medium lowercase',
      TAG_CLASSES[value]
    )}
  >
    {label}
  </div>
)
