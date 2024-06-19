import classNames from 'classnames'
import { FunctionComponent } from 'react'
import BatchId from './assets/batch-id.svg?react'
import Checkmark from './assets/checkmark.svg?react'
import Close from './assets/close.svg?react'
import Deployments from './assets/deployments.svg?react'
import Detections from './assets/detections.svg?react'
import Download from './assets/download.svg?react'
import Filters from './assets/filters.svg?react'
import GalleryView from './assets/gallery-view.svg?react'
import Images from './assets/images.svg?react'
import Info from './assets/info.svg?react'
import Members from './assets/members.svg?react'
import Occurrences from './assets/occurrences.svg?react'
import Overview from './assets/overview.svg?react'
import Photograph from './assets/photograph.svg?react'
import PlayButton from './assets/play-button.svg?react'
import RadixCheck from './assets/radix/check.svg?react'
import CircleBackslash from './assets/radix/circle-backslash.svg?react'
import RadixClock from './assets/radix/clock.svg?react'
import Cross from './assets/radix/cross.svg?react'
import Error from './assets/radix/error.svg?react'
import ExternalLink from './assets/radix/external-link.svg?react'
import HeartFilled from './assets/radix/heart-filled.svg?react'
import Heart from './assets/radix/heart.svg?react'
import Options from './assets/radix/options.svg?react'
import Pencil from './assets/radix/pencil.svg?react'
import Plus from './assets/radix/plus.svg?react'
import RadixQuestionMark from './assets/radix/question-mark.svg?react'
import RadixSearch from './assets/radix/search.svg?react'
import ToggleDown from './assets/radix/toggle-down.svg?react'
import ToggleLeft from './assets/radix/toggle-left.svg?react'
import ToggleRight from './assets/radix/toggle-right.svg?react'
import RadixTrash from './assets/radix/trash.svg?react'
import RadixUpdate from './assets/radix/update.svg?react'
import Sessions from './assets/sessions.svg?react'
import Settings from './assets/settings.svg?react'
import ShieldAlert from './assets/shield-alert.svg?react'
import ShieldCheck from './assets/shield-check.svg?react'
import Sort from './assets/sort.svg?react'
import Species from './assets/species.svg?react'
import TableView from './assets/table-view.svg?react'
import styles from './icon.module.scss'

export enum IconType {
  BatchId = 'batch-id',
  Checkmark = 'checkmark',
  CircleBackslash = 'circle-backslash',
  Close = 'close',
  Cross = 'cross',
  Deployments = 'deployments',
  Detections = 'detections',
  Download = 'download',
  Error = 'error',
  ExternalLink = 'external-link',
  Filters = 'filters',
  GalleryView = 'gallery-view',
  Heart = 'heart',
  HeartFilled = 'heart-filled',
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
  RadixClock = 'radix-clock',
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
  ToggleDown = 'toggle-down',
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
  [IconType.CircleBackslash]: CircleBackslash,
  [IconType.Close]: Close,
  [IconType.Cross]: Cross,
  [IconType.Deployments]: Deployments,
  [IconType.Detections]: Detections,
  [IconType.Download]: Download,
  [IconType.Error]: Error,
  [IconType.ExternalLink]: ExternalLink,
  [IconType.Filters]: Filters,
  [IconType.GalleryView]: GalleryView,
  [IconType.Heart]: Heart,
  [IconType.HeartFilled]: HeartFilled,
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
  [IconType.RadixClock]: RadixClock,
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
  [IconType.ToggleDown]: ToggleDown,
  [IconType.ToggleLeft]: ToggleLeft,
  [IconType.ToggleRight]: ToggleRight,
}

interface IconProps {
  size?: number
  theme?: IconTheme
  transform?: string
  type: IconType
}

export const Icon = ({
  size,
  theme = IconTheme.Dark,
  transform,
  type,
}: IconProps) => {
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
      style={{
        width: fixedSized ? `${size}px` : undefined,
        height: fixedSized ? `${size}px` : undefined,
        transform,
      }}
    >
      <Component />
    </div>
  )
}
