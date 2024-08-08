import * as _Slider from '@radix-ui/react-slider'
import classNames from 'classnames'
import _ from 'lodash'
import { useState } from 'react'
import { Tooltip } from '../tooltip/tooltip'
import { getThumbInBoundsOffset } from './getThumbInBoundsOffset'
import styles from './styles.module.scss'

interface ScoreSliderSliderProps {
  defaultValue: number
  label: string
  value: number
  onValueChange: (value: number) => void
  onValueCommit: (value: number) => void
}

export const ScoreSlider = ({
  defaultValue,
  label,
  value,
  onValueChange,
  onValueCommit,
}: ScoreSliderSliderProps) => {
  const [active, setActive] = useState(false)
  const percent = _.round(value * 100, 0)

  return (
    <div className={styles.scoreSlider}>
      <span className={styles.label}>{label}</span>
      <_Slider.Root
        className={styles.sliderRoot}
        defaultValue={[defaultValue]}
        min={0}
        max={1}
        step={0.01}
        value={[value]}
        onValueChange={(values) => onValueChange(values[0])}
        onValueCommit={(values) => onValueCommit(values[0])}
        onPointerDown={() => setActive(true)}
        onPointerUp={() => setActive(false)}
        onPointerLeave={() => {
          if (active) {
            onValueCommit(value)
          }
        }}
      >
        <_Slider.Track className={styles.sliderTrack}>
          <_Slider.Range className={styles.sliderRange} />
        </_Slider.Track>
        <DefaultValueThumb
          defaultValue={defaultValue}
          value={value}
          onClick={() => onValueCommit(defaultValue)}
        />
        <_Slider.Thumb className={styles.sliderThumb} />
      </_Slider.Root>
      <span className={styles.value}>{percent}%</span>
    </div>
  )
}

const DefaultValueThumb = ({
  defaultValue,
  value,
  onClick,
}: {
  defaultValue: number
  value: number
  onClick: () => void
}) => {
  const percent = _.round(defaultValue * 100, 0)

  return (
    <Tooltip content="Default threshold">
      <div
        className={classNames(styles.sliderThumb, styles.default, {
          [styles.primary]: value > defaultValue,
        })}
        onPointerDown={(e) => e.preventDefault()}
        onPointerUp={(e) => e.preventDefault()}
        style={{
          left: `calc(${percent}% + ${getThumbInBoundsOffset(20, percent)}px)`,
        }}
        onClick={onClick}
      />
    </Tooltip>
  )
}
