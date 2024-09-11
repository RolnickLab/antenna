import { CSSProperties } from 'react'
import styles from './license-info.module.scss'

const LINK = 'https://creativecommons.org/licenses/by-nc/4.0/legalcode'

interface LicenseInfoProps {
  style?: CSSProperties
}

export const LicenseInfo = ({ style }: LicenseInfoProps) => {
  // TODO: Check licence given the current project

  return (
    <p className={styles.text} style={style}>
      These images are licensed under <a href={LINK}>CC BY-NC 4.0</a>
    </p>
  )
}
