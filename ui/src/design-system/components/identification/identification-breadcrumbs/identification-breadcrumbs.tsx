import { Icon, IconTheme, IconType } from '../../icon/icon'
import styles from './identification-breadcrumbs.module.scss'

interface IdentificationBreadcrumbsProps {
  nodes: {
    id: string
    title: string
  }[]
}

export const IdentificationBreadcrumbs = ({
  nodes,
}: IdentificationBreadcrumbsProps) => (
  <div className={styles.breadcrumbs}>
    {nodes.map((node, index) => (
      <>
        <span key={index} className={styles.breadcrumb}>
          {node.title}
        </span>
        {index < nodes.length - 1 ? (
          <Icon
            type={IconType.ToggleRight}
            theme={IconTheme.Neutral}
            size={8}
          />
        ) : null}
      </>
    ))}
  </div>
)
