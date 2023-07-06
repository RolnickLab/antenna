import { ComponentMeta, ComponentStory } from '@storybook/react'
import { useState } from 'react'
import { CaptureList } from './capture-list'
import { CaptureRow } from './capture-row/capture-row'

type Meta = ComponentMeta<typeof CaptureList>
type Story = ComponentStory<typeof CaptureList>

export default {
  title: 'Components/CaptureList',
  component: CaptureList,
} as Meta

const TOTAL = 1000
const PAGE_SIZE = 20

const CaptureListTemplate: Story = () => {
  const [captures, setCaptures] = useState(generateCaptures(PAGE_SIZE))
  const [isLoading, setIsLoading] = useState(false)
  const [activeCaptureId, setActiveCaptureId] = useState(captures[0]?.id)
  const hasMore = captures.length < TOTAL

  const onNext = () => {
    if (!hasMore || isLoading) {
      return
    }

    // Fake async API call
    setIsLoading(true)
    setTimeout(() => {
      setCaptures([...captures, ...generateCaptures(PAGE_SIZE)])
      setIsLoading(false)
    }, 1000)
  }

  return (
    <div
      style={{
        width: '320px',
        height: '480px',
        position: 'relative',
        backgroundColor: '#222426',
      }}
    >
      <CaptureList hasMore={hasMore} onNext={onNext} numItems={captures.length}>
        {captures.map((capture) => (
          <CaptureRow
            key={capture.id}
            capture={capture}
            isActive={activeCaptureId === capture.id}
            onClick={() => setActiveCaptureId(capture.id)}
          />
        ))}
      </CaptureList>
    </div>
  )
}

export const Default = CaptureListTemplate.bind({})

// Help methods
const generateCaptures = (pageSize: number) =>
  Array.from({ length: pageSize }, generateCapture)

const generateCapture = () => {
  const id = (Math.random() + 1).toString(36).substring(7)
  const numDetections = Math.floor(Math.random() * 101)
  const scale = numDetections / 100
  const details = `${numDetections} detections(s)`

  return {
    id,
    details,
    scale,
    timeLabel: '00:00',
  }
}
