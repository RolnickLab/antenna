import classNames from 'classnames'
import { Icon, IconType } from 'design-system/components/icon/icon'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import styles from './blueprint-collection.module.scss'
import { LicenseInfo } from 'components/license-info/license-info'

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
      {items.map((item) =>
        item.to ? (
          <Link key={item.id} to={item.to} className={styles.blueprintItem}>
            <BlueprintItem item={item} />
          </Link>
        ) : (
          <div key={item.id} className={styles.blueprintItem}>
            <BlueprintItem item={item} />
          </div>
        )
      )}
    </div>
  </div>
)

const BlueprintItem = ({ item }: { item: BlueprintItem }) => {
  const [size, setSize] = useState({
    width: item.image.width,
    height: item.image.height,
  })

  return (
    <>
      <div className={styles.blueprintInfo} style={{ width: size.width }}>
        <span className={styles.count}>
          {item.countLabel?.length ? (
            <>
              <Icon type={IconType.Detections} size={12} />
              <span>{item.countLabel}</span>
            </>
          ) : null}
        </span>
        <span style={{ flex: 1 }} />
        <span>{item.timeLabel}</span>
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
      </div>
      <span className={styles.blueprintLabel}>{item.label}</span>
    </>
  )
}
