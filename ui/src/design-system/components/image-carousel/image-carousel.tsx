import classNames from 'classnames'
import {
  IconButton,
  IconButtonShape,
  IconButtonTheme,
} from 'design-system/components/icon-button/icon-button'
import { Icon, IconTheme, IconType } from 'design-system/components/icon/icon'
import { useEffect, useRef, useState } from 'react'
import styles from './image-carousel.module.scss'
import { CarouselTheme } from './types'
import { getImageBoxStyles, getPlaceholderStyles } from './utils'

interface ImageCarouselProps {
  images: {
    src: string
    alt?: string
  }[]
  theme?: CarouselTheme
  autoPlay?: boolean
  size?: {
    width: string | number
    ratio: number
  }
}

export const ImageCarousel = ({
  images,
  theme = CarouselTheme.Default,
  autoPlay,
  size,
}: ImageCarouselProps) => {
  if (images.length <= 1) {
    return <BasicImageCarousel image={images[0]} theme={theme} size={size} />
  }

  return (
    <MultiImageCarousel
      images={images}
      theme={theme}
      autoPlay={autoPlay}
      size={size}
    />
  )
}

const BasicImageCarousel = ({
  image,
  theme,
  size,
}: {
  image?: {
    src: string
    alt?: string
  }
  theme: CarouselTheme
  size?: {
    width: string | number
    ratio: number
  }
}) => (
  <div className={styles.container}>
    <div
      className={classNames(styles.imageBox, {
        [styles.light]: theme === CarouselTheme.Light,
      })}
      style={getImageBoxStyles(size?.width)}
    >
      <div style={getPlaceholderStyles(size?.ratio)} />
      <div className={classNames(styles.slide, styles.visible)}>
        {image ? (
          <img src={image.src + '?width=300&height=300'} alt={image.alt} className={styles.image} />
        ) : (
          <Icon
            type={IconType.Photograph}
            theme={IconTheme.Neutral}
            size={16}
          />
        )}
      </div>
    </div>
  </div>
)

const DURATION = 10000 // Change image every 10 second

const MultiImageCarousel = ({
  images,
  theme,
  autoPlay,
  size,
}: ImageCarouselProps) => {
  const [paused, setPaused] = useState(false)
  const [slideIndex, setSlideIndex] = useState(0)

  const slideIndexRef = useRef(slideIndex)
  const pausedRef = useRef(paused)

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
                <img src={image.src + '?width=300&height=300'} alt={image.alt} className={styles.image} />
              </div>
            )
          })}
        </div>
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
        <>
          <Icon type={IconType.Detections} size={12} />
          {paused ? (
            <span>
              {slideIndex + 1} / {images.length}
            </span>
          ) : (
            <span>{images.length}</span>
          )}
        </>
      </span>
    </div>
  )
}
