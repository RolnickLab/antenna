import classNames from 'classnames'
import { ReactComponent as BatchId } from './assets/batch-id.svg'
import { ReactComponent as Checkmark } from './assets/checkmark.svg'
import { ReactComponent as Deployments } from './assets/deployments.svg'
import { ReactComponent as Detections } from './assets/detections.svg'
import { ReactComponent as Download } from './assets/download.svg'
import { ReactComponent as Filters } from './assets/filters.svg'
import { ReactComponent as GalleryView } from './assets/gallery-view.svg'
import { ReactComponent as Identifiers } from './assets/identifiers.svg'
import { ReactComponent as Images } from './assets/images.svg'
import { ReactComponent as Info } from './assets/info.svg'
import { ReactComponent as Members } from './assets/members.svg'
import { ReactComponent as Occurrences } from './assets/occurrences.svg'
import { ReactComponent as Options } from './assets/options.svg'
import { ReactComponent as Overview } from './assets/overview.svg'
import { ReactComponent as PlayButton } from './assets/play-button.svg'
import { ReactComponent as Sessions } from './assets/sessions.svg'
import { ReactComponent as Sort } from './assets/sort.svg'
import { ReactComponent as TableView } from './assets/table-view.svg'
import { ReactComponent as ToggleLeft } from './assets/toggle-left.svg'
import { ReactComponent as ToggleRight } from './assets/toggle-right.svg'
import styles from './icon.module.scss'

export enum IconType {
  BatchId = 'batch-id',
  Checkmark = 'checkmark',
  Deployments = 'deployments',
  Detections = 'detections',
  Download = 'download',
  Filters = 'filters',
  GalleryView = 'gallery-view',
  Identifiers = 'identifiers',
  Images = 'images',
  Info = 'info',
  Members = 'members',
  Occurrences = 'occurrences',
  Options = 'options',
  Overview = 'overview',
  PlayButton = 'play-button',
  Sessions = 'sessions',
  Sort = 'sort',
  TableView = 'table-view',
  ToggleLeft = 'toggle-left',
  ToggleRight = 'toggle-right',
}

export enum IconTheme {
  Light = 'light',
  Dark = 'dark',
}

const COMPONENT_MAP = {
  [IconType.BatchId]: BatchId,
  [IconType.Checkmark]: Checkmark,
  [IconType.Deployments]: Deployments,
  [IconType.Detections]: Detections,
  [IconType.Download]: Download,
  [IconType.Filters]: Filters,
  [IconType.GalleryView]: GalleryView,
  [IconType.Identifiers]: Identifiers,
  [IconType.Images]: Images,
  [IconType.Info]: Info,
  [IconType.Members]: Members,
  [IconType.Occurrences]: Occurrences,
  [IconType.Options]: Options,
  [IconType.Overview]: Overview,
  [IconType.PlayButton]: PlayButton,
  [IconType.Sessions]: Sessions,
  [IconType.Sort]: Sort,
  [IconType.TableView]: TableView,
  [IconType.ToggleLeft]: ToggleLeft,
  [IconType.ToggleRight]: ToggleRight,
}

interface IconProps {
  type: IconType
  theme?: IconTheme
}

export const Icon = ({ type, theme = IconTheme.Dark }: IconProps) => {
  const Component = COMPONENT_MAP[type]

  return (
    <div
      className={classNames(styles.wrapper, {
        [styles.dark]: theme === IconTheme.Dark,
        [styles.light]: theme === IconTheme.Light,
      })}
    >
      <Component />
    </div>
  )
}
