import classNames from 'classnames'
import { IconButton } from 'design-system/components/icon-button/icon-button'
import { IconType } from 'design-system/components/icon/icon'
import { useEffect, useRef, useState } from 'react'
import { ImageCellTheme } from '../types'
import styles from './image-table-cell.module.scss'

interface ImageTableCellProps {
  images: {
    src: string
    alt?: string
  }[]
  theme?: ImageCellTheme
}

export const ImageTableCell = ({
  images,
  theme = ImageCellTheme.Default,
}: ImageTableCellProps) => {
  if (!images.length) {
    return <div className={styles.container} />
  }

  if (images.length === 1) {
    return <BasicImageTableCell image={images[0]} theme={theme} />
  }

  return <SlideshowImageTableCell images={images} theme={theme} />
}

const BasicImageTableCell = ({
  image,
  theme,
}: {
  image: {
    src: string
    alt?: string
  }
  theme: ImageCellTheme
}) => (
  <div className={styles.container}>
    <div
      className={classNames(styles.imageBox, {
        [styles.light]: theme === ImageCellTheme.Light,
      })}
    >
      <img src={image.src} alt={image.alt} className={styles.image} />
    </div>
  </div>
)

const SlideshowImageTableCell = ({ images, theme }: ImageTableCellProps) => {
  const [paused, setPaused] = useState(false)
  const [slideIndex, setSlideIndex] = useState(0)

  const slideIndexRef = useRef(slideIndex)
  const pausedRef = useRef(paused)

  useEffect(() => {
    const interval = setInterval(() => {
      if (!pausedRef.current) {
        showNext(slideIndexRef.current)
      }
    }, 2000)

    return () => clearInterval(interval)
  }, [])

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
            iconType={IconType.ToggleLeft}
            onClick={() => showPrev(slideIndex)}
          />
        </div>
        <div
          className={classNames(styles.imageBox, {
            [styles.light]: theme === ImageCellTheme.Light,
          })}
        >
          {images.map((image, index) => (
            <div
              key={index}
              className={classNames(styles.slide, {
                [styles.visible]: index === slideIndex,
              })}
            >
              <img src={image.src} alt={image.alt} className={styles.image} />
            </div>
          ))}
        </div>
        <div
          className={classNames(styles.control, {
            [styles.visible]: paused,
          })}
        >
          <IconButton
            iconType={IconType.ToggleRight}
            onClick={() => showNext(slideIndex)}
          />
        </div>
      </div>
      <span
        className={classNames(styles.label, styles.control, {
          [styles.visible]: paused,
        })}
      >
        {slideIndex + 1} / {images.length}
      </span>
    </div>
  )
}
