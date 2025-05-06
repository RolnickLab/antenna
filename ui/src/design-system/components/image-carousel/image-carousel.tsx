import classNames from 'classnames'
import {
  IconButton,
  IconButtonShape,
  IconButtonTheme,
} from 'design-system/components/icon-button/icon-button'
import { Icon, IconTheme, IconType } from 'design-system/components/icon/icon'
import { ReactNode, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { getTotalLabel } from 'utils/numberFormats'
import styles from './image-carousel.module.scss'
import { CarouselTheme } from './types'
import { getImageBoxStyles, getPlaceholderStyles } from './utils'
import { LicenseInfo } from 'components/license-info/license-info'

interface ImageCarouselProps {
  autoPlay?: boolean
  images: {
    src: string
    alt?: string
  }[]
  showLicenseInfo?: boolean
  size?: {
    width: string | number
    ratio: number
  }
  theme?: CarouselTheme
  total?: number
  to?: string
}

export const ImageCarousel = ({
  autoPlay,
  images,
  showLicenseInfo,
  size,
  theme = CarouselTheme.Default,
  total,
  to,
}: ImageCarouselProps) => {
  if (images.length <= 1) {
    return (
      <BasicImageCarousel
        image={images[0]}
        showLicenseInfo={showLicenseInfo}
        size={size}
        theme={theme}
        to={to}
      />
    )
  }

  return (
    <MultiImageCarousel
      autoPlay={autoPlay}
      images={images}
      showLicenseInfo={showLicenseInfo}
      size={size}
      theme={theme}
      total={total}
      to={to}
    />
  )
}

const BasicImageCarousel = ({
  image,
  showLicenseInfo,
  size,
  theme,
  to,
}: {
  image?: {
    src: string
    alt?: string
  }
  showLicenseInfo?: boolean
  size?: {
    width: string | number
    ratio: number
  }
  theme: CarouselTheme
  to?: string
}) => (
  <div className={styles.container}>
    <ConditionalLink to={to}>
      <div
        className={classNames(styles.imageBox, {
          [styles.light]: theme === CarouselTheme.Light,
        })}
        style={getImageBoxStyles(size?.width)}
      >
        <div style={getPlaceholderStyles(size?.ratio)} />
        <div className={classNames(styles.slide, styles.visible)}>
          {image ? (
            <img src={image.src} alt={image.alt} className={styles.image} />
          ) : (
            <Icon
              type={IconType.Photograph}
              theme={IconTheme.Neutral}
              size={16}
            />
          )}
        </div>
      </div>
    </ConditionalLink>
    {showLicenseInfo && <LicenseInfo style={{ marginTop: '32px' }} />}
  </div>
)

const DURATION = 10000 // Change image every 10 second

const MultiImageCarousel = ({
  autoPlay,
  images,
  showLicenseInfo,
  size,
  theme,
  total,
  to,
}: ImageCarouselProps) => {
  const [paused, setPaused] = useState(false)
  const [slideIndex, setSlideIndex] = useState(0)

  const slideIndexRef = useRef(slideIndex)
  const pausedRef = useRef(paused)

  const totalLabel = getTotalLabel(images.length, total)

  useEffect(() => {
    if (!autoPlay) {
      return
    }

    const interval = setInterval(() => {
      if (!pausedRef.current) {
        showNext(slideIndexRef.current)
      }
    }, DURATION)

    return () => clearInterval(interval)
  }, [autoPlay])

  useEffect(() => {
    slideIndexRef.current = slideIndex
  }, [slideIndex])

  useEffect(() => {
    pausedRef.current = paused
  }, [paused])

  const showNext = (currentIndex: number) => {
    const nextIndex = currentIndex + 1
    if (nextIndex >= images.length) {
      setSlideIndex(0)
    } else {
      setSlideIndex(nextIndex)
    }
  }

  const showPrev = (currentIndex: number) => {
    const prevIndex = currentIndex - 1
    if (prevIndex < 0) {
      setSlideIndex(images.length - 1)
    } else {
      setSlideIndex(prevIndex)
    }
  }

  return (
    <div
      className={styles.container}
      onMouseOver={() => setPaused(true)}
      onMouseOut={() => setPaused(false)}
    >
      <div className={styles.row}>
        <div
          className={classNames(styles.control, {
            [styles.visible]: paused,
          })}
        >
          <IconButton
            icon={IconType.ToggleLeft}
            shape={IconButtonShape.Round}
            theme={IconButtonTheme.Success}
            onClick={() => showPrev(slideIndex)}
          />
        </div>
        <ConditionalLink to={to}>
          <div
            className={classNames(styles.imageBox, {
              [styles.light]: theme === CarouselTheme.Light,
            })}
            style={getImageBoxStyles(size?.width)}
          >
            <div style={getPlaceholderStyles(size?.ratio)} />
            {images.map((image, index) => {
              const render =
                index === 0 || // Always render first slide
                index === images.length - 1 || // Always render last image
                Math.abs(index - slideIndex) <= 1 // Render nearby slides

              if (!render) {
                return
              }

              return (
                <div
                  key={index}
                  className={classNames(styles.slide, {
                    [styles.visible]: index === slideIndex,
                  })}
                >
                  <img
                    src={image.src}
                    alt={image.alt}
                    className={styles.image}
                  />
                </div>
              )
            })}
          </div>
        </ConditionalLink>
        <div
          className={classNames(styles.control, {
            [styles.visible]: paused,
          })}
        >
          <IconButton
            icon={IconType.ToggleRight}
            shape={IconButtonShape.Round}
            theme={IconButtonTheme.Success}
            onClick={() => showNext(slideIndex)}
          />
        </div>
      </div>
      <span className={styles.info}>
        {slideIndex + 1} / {totalLabel}
      </span>
      {showLicenseInfo && <LicenseInfo style={{ marginTop: '32px' }} />}
    </div>
  )
}

const ConditionalLink = ({
  to,
  children,
}: {
  to?: string
  children: ReactNode
}) => {
  if (!to) {
    return <>{children}</>
  }

  return <Link to={to}>{children}</Link>
}
