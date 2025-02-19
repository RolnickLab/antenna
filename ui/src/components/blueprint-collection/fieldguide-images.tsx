import classNames from 'classnames'
import styles from './blueprint-collection.module.scss'

export interface FieldguideImagesProps {
  categoryId?: string
  images: {
    photo_id: string
    image_url: string
    copyright: string
  }[]
}

export const FieldguideImages = ({
  categoryId,
  images,
}: FieldguideImagesProps) => (
  <div
    className={classNames(styles.blueprint, {
      [styles.empty]: images.length === 0,
    })}
  >
    <div className={styles.blueprintContent}>
      {images.map((image) => (
        <div key={image.photo_id} className={styles.blueprintItem}>
          <div className={styles.blueprintImage}>
            <img src={image.image_url} alt="" />
          </div>
          <span className={styles.blueprintLabel}>© {image.copyright}</span>
        </div>
      ))}
    </div>
    {categoryId ? (
      <div className={styles.licenseInfoContent}>
        <p className="text-center body-small">
          Images from{' '}
          <a
            href={`https://leps.fieldguide.ai/figures?category=${categoryId}`}
            rel="noreferrer"
            target="_blank"
          >
            Fieldguide
          </a>
        </p>
      </div>
    ) : null}
  </div>
)
