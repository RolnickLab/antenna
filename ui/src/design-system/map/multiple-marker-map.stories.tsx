import { ComponentMeta, ComponentStory } from '@storybook/react'
import { MarkerPosition, MultipleMarkerMap } from './multiple-marker-map'

type Meta = ComponentMeta<typeof MultipleMarkerMap>
type Story = ComponentStory<typeof MultipleMarkerMap>

const DEFAULT_MARKER_POSITIONS = [
  { position: new MarkerPosition(52.30767, 5.04011) },
  { position: new MarkerPosition(52.31767, 5.06011) },
  { position: new MarkerPosition(52.32767, 5.09011) },
]

export default {
  title: 'Components/MultipleMarkerMap',
  component: MultipleMarkerMap,
} as Meta

export const Default: Story = () => (
  <MultipleMarkerMap markers={DEFAULT_MARKER_POSITIONS} />
)
