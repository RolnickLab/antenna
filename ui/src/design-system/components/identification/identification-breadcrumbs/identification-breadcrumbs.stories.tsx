import { ComponentMeta } from '@storybook/react'
import { IdentificationBreadcrumbs } from './identification-breadcrumbs'

type Meta = ComponentMeta<typeof IdentificationBreadcrumbs>

export default {
  title: 'Components/Identification/IdentificationBreadcrumbs',
  component: IdentificationBreadcrumbs,
} as Meta

export const Default: Meta = {
  args: {
    items: [
      { id: 'erebidae', name: 'Erebidae', rank: 'Family' },
      { id: 'arctiinae', name: 'Arctiinae', rank: 'Genus' },
      { id: 'lithosiini', name: 'Lithosiini', rank: 'Species' },
    ],
  },
}
