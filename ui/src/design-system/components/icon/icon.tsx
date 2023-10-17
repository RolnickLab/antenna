import classNames from 'classnames'
import { FunctionComponent } from 'react'
import { ReactComponent as BatchId } from './assets/batch-id.svg'
import { ReactComponent as Checkmark } from './assets/checkmark.svg'
import { ReactComponent as Close } from './assets/close.svg'
import { ReactComponent as Deployments } from './assets/deployments.svg'
import { ReactComponent as Detections } from './assets/detections.svg'
import { ReactComponent as Download } from './assets/download.svg'
import { ReactComponent as Filters } from './assets/filters.svg'
import { ReactComponent as GalleryView } from './assets/gallery-view.svg'
import { ReactComponent as Images } from './assets/images.svg'
import { ReactComponent as Info } from './assets/info.svg'
import { ReactComponent as Members } from './assets/members.svg'
import { ReactComponent as Occurrences } from './assets/occurrences.svg'
import { ReactComponent as Overview } from './assets/overview.svg'
import { ReactComponent as Photograph } from './assets/photograph.svg'
import { ReactComponent as PlayButton } from './assets/play-button.svg'
import { ReactComponent as RadixCheck } from './assets/radix/check.svg'
import { ReactComponent as Cross } from './assets/radix/cross.svg'
import { ReactComponent as Error } from './assets/radix/error.svg'
import { ReactComponent as Options } from './assets/radix/options.svg'
import { ReactComponent as Pencil } from './assets/radix/pencil.svg'
import { ReactComponent as Plus } from './assets/radix/plus.svg'
import { ReactComponent as RadixQuestionMark } from './assets/radix/question-mark.svg'
import { ReactComponent as RadixSearch } from './assets/radix/search.svg'
import { ReactComponent as ToggleLeft } from './assets/radix/toggle-left.svg'
import { ReactComponent as ToggleRight } from './assets/radix/toggle-right.svg'
import { ReactComponent as RadixTrash } from './assets/radix/trash.svg'
import { ReactComponent as RadixUpdate } from './assets/radix/update.svg'
import { ReactComponent as Sessions } from './assets/sessions.svg'
import { ReactComponent as Settings } from './assets/settings.svg'
import { ReactComponent as ShieldAlert } from './assets/shield-alert.svg'
import { ReactComponent as ShieldCheck } from './assets/shield-check.svg'
import { ReactComponent as Sort } from './assets/sort.svg'
import { ReactComponent as Species } from './assets/species.svg'
import { ReactComponent as TableView } from './assets/table-view.svg'
import styles from './icon.module.scss'

export enum IconType {
  BatchId = 'batch-id',
  Checkmark = 'checkmark',
  Close = 'close',
  Cross = 'cross',
  Deployments = 'deployments',
  Detections = 'detections',
  Download = 'download',
  Error = 'error',
  Filters = 'filters',
  GalleryView = 'gallery-view',
  Images = 'images',
  Info = 'info',
  Members = 'members',
  Occurrences = 'occurrences',
  Options = 'options',
  Overview = 'overview',
  Pencil = 'pencil',
  Photograph = 'photograph',
  PlayButton = 'play-button',
  Plus = 'plus',
  RadixCheck = 'radix-check',
  RadixQuestionMark = 'radix-question-mark',
  RadixSearch = 'radix-search',
  RadixTrash = 'radix-trash',
  RadixUpdate = 'radix-update',
  Sessions = 'sessions',
  Settings = 'settings',
  ShieldAlert = 'shield-alert',
  ShieldCheck = 'shield-check',
  Sort = 'sort',
  Species = 'species',
  TableView = 'table-view',
  ToggleLeft = 'toggle-left',
  ToggleRight = 'toggle-right',
}

export enum IconTheme {
  Light = 'light',
  Neutral = 'neutral',
  Dark = 'dark',
  Primary = 'primary',
  Success = 'success',
  Error = 'error',
}

const COMPONENT_MAP: { [key in IconType]: FunctionComponent } = {
  [IconType.BatchId]: BatchId,
  [IconType.Checkmark]: Checkmark,
  [IconType.Close]: Close,
  [IconType.Cross]: Cross,
  [IconType.Deployments]: Deployments,
  [IconType.Detections]: Detections,
  [IconType.Download]: Download,
  [IconType.Error]: Error,
  [IconType.Filters]: Filters,
  [IconType.GalleryView]: GalleryView,
  [IconType.Images]: Images,
  [IconType.Info]: Info,
  [IconType.Members]: Members,
  [IconType.Occurrences]: Occurrences,
  [IconType.Options]: Options,
  [IconType.Overview]: Overview,
  [IconType.Pencil]: Pencil,
  [IconType.Photograph]: Photograph,
  [IconType.PlayButton]: PlayButton,
  [IconType.Plus]: Plus,
  [IconType.RadixCheck]: RadixCheck,
  [IconType.RadixQuestionMark]: RadixQuestionMark,
  [IconType.RadixSearch]: RadixSearch,
  [IconType.RadixTrash]: RadixTrash,
  [IconType.RadixUpdate]: RadixUpdate,
  [IconType.Sessions]: Sessions,
  [IconType.Settings]: Settings,
  [IconType.ShieldAlert]: ShieldAlert,
  [IconType.ShieldCheck]: ShieldCheck,
  [IconType.Sort]: Sort,
  [IconType.Species]: Species,
  [IconType.TableView]: TableView,
  [IconType.ToggleLeft]: ToggleLeft,
  [IconType.ToggleRight]: ToggleRight,
}

interface IconProps {
  type: IconType
  theme?: IconTheme
  size?: number
}

export const Icon = ({ type, theme = IconTheme.Dark, size }: IconProps) => {
  const Component = COMPONENT_MAP[type]
  const fixedSized = size !== undefined

  return (
    <div
      className={classNames(styles.wrapper, {
        [styles.light]: theme === IconTheme.Light,
        [styles.dark]: theme === IconTheme.Dark,
        [styles.neutral]: theme === IconTheme.Neutral,
        [styles.primary]: theme === IconTheme.Primary,
        [styles.success]: theme === IconTheme.Success,
        [styles.error]: theme === IconTheme.Error,
        [styles.fixedSized]: fixedSized,
      })}
      style={
        fixedSized
          ? {
              width: `${size}px`,
              height: `${size}px`,
            }
          : undefined
      }
    >
      <Component />
    </div>
  )
}
