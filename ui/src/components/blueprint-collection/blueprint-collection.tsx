import classNames from 'classnames'
import { LicenseInfo } from 'components/license-info/license-info'
import { Icon, IconType } from 'design-system/components/icon/icon'
import { EyeIcon } from 'lucide-react'
import { buttonVariants, Tooltip } from 'nova-ui-kit'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import styles from './blueprint-collection.module.scss'

export interface BlueprintItem {
  id: string
  image: { src: string; width: number; height: number }
  label: string
  timeLabel: string
  countLabel: string
  to?: string
}

export const BlueprintCollection = ({ items }: { items: BlueprintItem[] }) => (
  <div
    className={classNames(styles.blueprint, {
      [styles.empty]: items.length === 0,
    })}
  >
    <div className={styles.licenseInfoContent}>
      <LicenseInfo />
    </div>
    <div className={styles.blueprintContent}>
      {items.map((item) => (
        <BlueprintItem key={item.id} item={item} />
      ))}
    </div>
  </div>
)

const BlueprintItem = ({ item }: { item: BlueprintItem }) => {
  const [size, setSize] = useState({
    width: item.image.width,
    height: item.image.height,
  })

  return (
    <div className={classNames(styles.blueprintItem, 'group')}>
      <div className={styles.blueprintInfo} style={{ width: size.width }}>
        {item.countLabel?.length ? (
          <span className={styles.count}>
            <Icon type={IconType.Detections} size={12} />
            <span>{item.countLabel}</span>
          </span>
        ) : null}
        <span className="grow text-muted-foreground text-right">
          {item.timeLabel}
        </span>
      </div>
      <div className={styles.blueprintImage}>
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
          <Tooltip.Provider delayDuration={0}>
            <Tooltip.Root>
              <Tooltip.Trigger asChild>
                <Link
                  to={item.to}
                  className={classNames(
                    buttonVariants({ size: 'icon', variant: 'outline' }),
                    'hidden w-8 h-8 absolute right-2 bottom-2 group-hover:flex'
                  )}
                >
                  <EyeIcon className="w-4 h-4" />
                </Link>
              </Tooltip.Trigger>
              <Tooltip.Content side="bottom">
                <span>Show in session capture</span>
              </Tooltip.Content>
            </Tooltip.Root>
          </Tooltip.Provider>
        ) : null}
      </div>
      <span
        className={classNames(
          styles.blueprintLabel,
          'body-small text-foreground'
        )}
      >
        {item.label}
      </span>
    </div>
  )
}
