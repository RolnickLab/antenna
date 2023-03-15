import { Icon, IconTheme, IconType } from '../icon/icon'
import styles from './icon-button.module.scss'

interface IconButtonProps {
  iconType: IconType
  onClick: () => void
}

export const IconButton = ({ iconType, onClick }: IconButtonProps) => {
  return (
    <button className={styles.iconButton} onClick={onClick}>
      <Icon type={iconType} theme={IconTheme.Light} size={12} />
    </button>
  )
}
