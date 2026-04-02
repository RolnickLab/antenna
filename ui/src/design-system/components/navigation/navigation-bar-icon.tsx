import classNames from 'classnames'
import { FunctionComponent } from 'react'
import Captures from './assets/captures.svg?react'
import Deployments from './assets/deployments.svg?react'
import Jobs from './assets/jobs.svg?react'
import Occurrences from './assets/occurrences.svg?react'
import Project from './assets/project.svg?react'
import Sessions from './assets/sessions.svg?react'
import Taxa from './assets/taxa.svg?react'
import styles from './navigation-bar.module.scss'

const ICON_MAP: { [id: string]: FunctionComponent } = {
  captures: Captures,
  deployments: Deployments,
  jobs: Jobs,
  occurrences: Occurrences,
  project: Project,
  sessions: Sessions,
  taxa: Taxa,
}

export const NavigationBarIcon = ({
  isActive,
  id,
}: {
  isActive?: boolean
  id: string
}) => {
  const Icon = ICON_MAP[id]

  if (!Icon) {
    return null
  }

  return (
    <div
      className={classNames(styles.icon, {
        [styles.active]: isActive,
      })}
    >
      <Icon />
    </div>
  )
}
