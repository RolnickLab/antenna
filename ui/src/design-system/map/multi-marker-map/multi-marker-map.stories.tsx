import { ComponentMeta, ComponentStory } from '@storybook/react'
import { MarkerPosition } from '../types'
import { MultiMarkerMap } from './multi-marker-map'

type Meta = ComponentMeta<typeof MultiMarkerMap>
type Story = ComponentStory<typeof MultiMarkerMap>

const DEFAULT_MARKER_POSITIONS = [
  { position: new MarkerPosition(52.30767, 5.04011) },
  { position: new MarkerPosition(52.31767, 5.06011) },
  { position: new MarkerPosition(52.32767, 5.09011) },
]

export default {
  title: 'Components/Map/MultiMarkerMap',
  component: MultiMarkerMap,
} as Meta

export const Default: Story = () => (
  <MultiMarkerMap markers={DEFAULT_MARKER_POSITIONS} />
)
