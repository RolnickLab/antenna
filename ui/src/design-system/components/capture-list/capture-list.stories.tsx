import { ComponentMeta, ComponentStory } from '@storybook/react'
import { useMemo, useState } from 'react'
import { CaptureList } from './capture-list'
import { CaptureRow } from './capture-row/capture-row'

type Meta = ComponentMeta<typeof CaptureList>
type Story = ComponentStory<typeof CaptureList>

export default {
  title: 'Components/CaptureList',
  component: CaptureList,
} as Meta

const NUM_CAPTURES = 100

const CaptureListTemplate: Story = () => {
  const captures = useMemo(
    () =>
      Array.from({ length: NUM_CAPTURES }, (_, i) =>
        generateCapture(`capture-${i}`)
      ),
    []
  )

  const [activeCaptureId, setActiveCaptureId] = useState(captures[0]?.id)

  return (
    <div
      style={{
        width: '320px',
        height: '480px',
        position: 'relative',
        backgroundColor: '#222426',
      }}
    >
      <CaptureList>
        {captures.map((capture) => (
          <CaptureRow
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
const generateCapture = (id: string) => {
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
