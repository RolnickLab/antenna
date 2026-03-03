import classNames from 'classnames'
import { Icon, IconTheme, IconType } from 'design-system/components/icon/icon'
import { BasicTooltip } from 'design-system/components/tooltip/basic-tooltip'
import styles from './status-info.module.scss'
import { Status } from './types'

const statusInfo: {
  [key in Status]: { icon?: IconType; className: string }
} = {
  [Status.NotConnected]: {
    icon: IconType.RadixQuestionMark,
    className: styles.notConnected,
  },
  [Status.Connecting]: {
    className: styles.connecting,
  },
  [Status.Connected]: {
    icon: IconType.RadixCheck,
    className: styles.connected,
  },
}

export const StatusInfo = ({
  status,
  tooltip,
}: {
  status: Status
  tooltip?: string
}) => {
  const info = statusInfo[status]

  return (
    <div className={styles.wrapper}>
      <BasicTooltip content={tooltip}>
        <div className={styles.content}>
          <div className={classNames(styles.iconContainer, info.className)}>
            {info.icon && (
              <Icon size={10} type={info.icon} theme={IconTheme.Dark} />
            )}
          </div>
        </div>
      </BasicTooltip>
    </div>
  )
}
