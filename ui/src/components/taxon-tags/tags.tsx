import classNames from 'classnames'
import { Tag } from './tag'
import { TagData } from './types'

export const Tags = ({
  className,
  tags,
}: {
  className?: string
  tags: TagData[]
}) => (
  <div className={classNames('flex flex-wrap gap-1', className)}>
    {tags.map((tag) => (
      <Tag key={tag.value} {...tag} />
    ))}
  </div>
)
