import classNames from 'classnames'
import {
  IconButton,
  IconButtonTheme,
} from 'design-system/components/icon-button/icon-button'
import { Icon, IconTheme, IconType } from 'design-system/components/icon/icon'
import { Tooltip } from 'design-system/components/tooltip/tooltip'
import { STRING, translate } from 'utils/language'
import styles from './connection-status.module.scss'
import { Status } from './types'

const statusInfo: {
  [key in Status]: { label: string; icon?: IconType; className: string }
} = {
  [Status.NotConnected]: {
    label: translate(STRING.NOT_CONNECTED),
    icon: IconType.RadixQuestionMark,
    className: styles.notConnected,
  },
  [Status.Connecting]: {
    label: translate(STRING.CONNECTING),
    className: styles.connecting,
  },
  [Status.Connected]: {
    label: translate(STRING.CONNECTED),
    icon: IconType.RadixCheck,
    className: styles.connected,
  },
}

export const ConnectionStatus = ({
  label,
  status,
  onRefreshClick,
  tooltip,
}: {
  label?: string
  status: Status
  onRefreshClick: () => void
  tooltip?: string
}) => {
  const info = statusInfo[status]

  return (
    <div className={styles.wrapper}>
      <div className={styles.titleRow}>
        <div className={styles.titleRowContent}>
          <span>Connection URI</span>
          <div className={styles.buttonContainer}>
            <IconButton
              icon={IconType.RadixUpdate}
              theme={IconButtonTheme.Plain}
              title={translate(STRING.REFRESH)}
              onClick={onRefreshClick}
            />
          </div>
        </div>
      </div>

      <div className={styles.infoRow}>
        <Tooltip content={tooltip}>
          <div className={styles.infoRowContent}>
            <div className={classNames(styles.iconContainer, info.className)}>
              {info.icon && (
                <Icon size={10} type={info.icon} theme={IconTheme.Dark} />
              )}
            </div>
            <span>{label ?? info.label}</span>
          </div>
        </Tooltip>
      </div>
    </div>
  )
}
