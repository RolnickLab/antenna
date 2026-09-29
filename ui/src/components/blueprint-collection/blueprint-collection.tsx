import classNames from 'classnames'
import { LicenseInfo } from 'components/license-info/license-info'
import { ChevronRightIcon } from 'lucide-react'
import { buttonVariants } from 'nova-ui-kit'
import { cn } from 'nova-ui-kit/utils'
import { ReactNode, useState } from 'react'
import { Link } from 'react-router-dom'
import { STRING, translate } from 'utils/language'
import styles from './blueprint-collection.module.scss'
import { missingCropSize } from './crop-size'

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
  filmStrip,
  showLicenseInfo,
}: {
  children: ReactNode
  /** Lay the children out as a divided vertical run; pick this for lists of frames. */
  filmStrip?: boolean
  showLicenseInfo?: boolean
}) => (
  <div className={classNames(styles.blueprint)}>
    {showLicenseInfo ? (
      <div className={styles.licenseInfoContent}>
        <LicenseInfo />
      </div>
    ) : null}
    <div
      className={classNames(styles.blueprintContent, {
        [styles.filmStrip]: filmStrip,
      })}
    >
      {children}
    </div>
  </div>
)

/**
 * The frame's crop, or an empty box with the bounding box's proportions when the crop
 * was never made or no longer loads, so the frame still reads as a detection.
 */
const CropImage = ({
  image,
}: {
  image: { src?: string | null; width: number; height: number }
}) => {
  const [failed, setFailed] = useState(false)

  if (image.src && !failed) {
    return (
      <img
        src={image.src}
        alt=""
        width={image.width}
        height={image.height}
        onError={() => setFailed(true)}
      />
    )
  }

  return (
    <div
      className={styles.missingCrop}
      role="img"
      aria-label={translate(STRING.TRACK_FRAME_NO_CROP)}
      title={translate(STRING.TRACK_FRAME_NO_CROP)}
      style={missingCropSize(image.width, image.height)}
    />
  )
}

export const BlueprintItem = ({
  actions,
  caption,
  item,
  onLinkClick,
}: {
  actions?: ReactNode
  caption?: ReactNode
  onLinkClick?: () => void
  item: {
    id: string
    image: { src: string; width: number; height: number }
    label: string
    timeLabel: string
    countLabel: string
    to?: string
  }
}) => (
  <div className={classNames(styles.blueprintItem, 'group')}>
    <div className={styles.crop}>
      <CropImage image={item.image} />
    </div>
    {/* The details take the rest of the row, so their width never follows the crop's. */}
    <div className="flex flex-col grow min-w-0 gap-1">
      {caption ?? (
        <span className="body-small text-muted-foreground">
          {item.timeLabel}
        </span>
      )}
      <div className="flex items-center gap-1">
        {item.to ? (
          <Link
            className={cn(
              buttonVariants({ size: 'small', variant: 'ghost' }),
              'px-2 -ml-2'
            )}
            onClick={onLinkClick}
            to={item.to}
          >
            <span>{translate(STRING.VIEW_IN_SESSION)}</span>
            <ChevronRightIcon className="w-4 h-4" />
          </Link>
        ) : null}
        {actions}
      </div>
    </div>
  </div>
)
