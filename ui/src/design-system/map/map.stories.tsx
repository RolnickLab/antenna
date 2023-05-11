import { ComponentMeta, ComponentStory } from '@storybook/react'
import { useState } from 'react'
import { Map, MarkerPosition } from './map'

type Meta = ComponentMeta<typeof Map>
type Story = ComponentStory<typeof Map>

const DEFAULT_MARKER_POSITION = new MarkerPosition(52.30767, 5.04011)

export default {
  title: 'Components/Map',
  component: Map,
} as Meta

export const Default: Story = () => (
  <Map
    center={DEFAULT_MARKER_POSITION}
    markerPosition={DEFAULT_MARKER_POSITION}
  />
)

export const WithDraggableMarker: Story = () => {
  const [markerPosition, setMarkerPosition] = useState(DEFAULT_MARKER_POSITION)

  return (
    <Map
      center={markerPosition}
      markerPosition={markerPosition}
      markerDraggable
      onMarkerPositionChange={setMarkerPosition}
    />
  )
}
