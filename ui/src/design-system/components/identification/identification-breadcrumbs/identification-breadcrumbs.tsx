import { Tooltip } from 'design-system/components/tooltip/tooltip'
import { Fragment } from 'react'
import { Icon, IconTheme, IconType } from '../../icon/icon'
import styles from './identification-breadcrumbs.module.scss'

interface IdentificationBreadcrumbsProps {
  items: {
    id: string
    name: string
    rank: string
    to?: string
  }[]
}

export const IdentificationBreadcrumbs = ({
  items,
}: IdentificationBreadcrumbsProps) => (
  <div className={styles.breadcrumbs}>
    {items.map((item, index) => (
      <Fragment key={item.id}>
        <Tooltip content={item.rank} to={item.to}>
          <span className={styles.breadcrumb}>{item.name}</span>
        </Tooltip>
        {index < items.length - 1 ? (
          <Icon
            type={IconType.ToggleRight}
            theme={IconTheme.Neutral}
            size={8}
          />
        ) : null}
      </Fragment>
    ))}
  </div>
)
