import { CSSProperties } from 'react'

const LINK = 'https://creativecommons.org/licenses/by-nc/4.0/legalcode'

interface LicenseInfoProps {
  style?: CSSProperties
}

export const LicenseInfo = ({ style }: LicenseInfoProps) => {
  // TODO: Check licence given the current project

  return (
    <p className="body-small text-muted-foreground" style={style}>
      These images are licensed under{' '}
      <a href={LINK} className="font-semibold text-primary-500">
        CC BY-NC 4.0
      </a>
    </p>
  )
}
