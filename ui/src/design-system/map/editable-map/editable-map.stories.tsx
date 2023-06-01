import { ComponentMeta, ComponentStory } from '@storybook/react'
import { useRef, useState } from 'react'
import { MarkerPosition, Map } from '../types'
import { EditableMap } from './editable-map'

type Meta = ComponentMeta<typeof EditableMap>
type Story = ComponentStory<typeof EditableMap>

const DEFAULT_MARKER_POSITION = new MarkerPosition(52.30767, 5.04011)

export default {
  title: 'Components/Map/EditableMap',
  component: EditableMap,
} as Meta

export const Default: Story = () => {
  const mapRef = useRef<Map>(null)
  const [markerPosition, setMarkerPosition] = useState(DEFAULT_MARKER_POSITION)

  return (
    <EditableMap
      center={DEFAULT_MARKER_POSITION}
      mapRef={mapRef}
      markerPosition={markerPosition}
      onMarkerPositionChange={setMarkerPosition}
    />
  )
}
