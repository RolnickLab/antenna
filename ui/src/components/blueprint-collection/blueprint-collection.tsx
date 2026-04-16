import classNames from 'classnames'
import { LicenseInfo } from 'components/license-info/license-info'
import { ChevronRightIcon } from 'lucide-react'
import { buttonVariants } from 'nova-ui-kit'
import { ReactNode, useState } from 'react'
import { Link } from 'react-router-dom'
import { STRING, translate } from 'utils/language'
import styles from './blueprint-collection.module.scss'

export interface BlueprintItem {
  id: string
  image: { src: string; width: number; height: number }
  label: string
  timeLabel: string
  countLabel: string
  to?: string
}

export const BlueprintCollection = ({
  children,
  showLicenseInfo,
}: {
  children: ReactNode
  showLicenseInfo?: boolean
}) => (
  <div className={classNames(styles.blueprint)}>
    {showLicenseInfo ? (
      <div className={styles.licenseInfoContent}>
        <LicenseInfo />
      </div>
    ) : null}
    <div className={styles.blueprintContent}>{children}</div>
  </div>
)

export const BlueprintItem = ({
  item,
}: {
  item: {
    id: string
    image: { src: string; width: number; height: number }
    label: string
    timeLabel: string
    countLabel: string
    to?: string
  }
}) => {
  const [size, setSize] = useState({
    width: item.image.width,
    height: item.image.height,
  })

  return (
    <div className={classNames(styles.blueprintItem, 'group')}>
      <div className={styles.blueprintInfo} style={{ width: size.width }}>
        <span className="grow text-muted-foreground text-right">
          {item.timeLabel}
        </span>
      </div>
      <div className="flex flex-col items-center gap-2">
        <img
          src={item.image.src}
          alt=""
          width={size.width}
          height={size.height}
          onLoad={(e) => {
            setSize({
              width: e.currentTarget.width,
              height: e.currentTarget.height,
            })
          }}
        />
        {item.to ? (
          <Link
            className={buttonVariants({ size: 'small', variant: 'ghost' })}
            to={item.to}
          >
            <span>{translate(STRING.VIEW_IN_SESSION)}</span>
            <ChevronRightIcon className="w-4 h-4" />
          </Link>
        ) : null}
      </div>
    </div>
  )
}
