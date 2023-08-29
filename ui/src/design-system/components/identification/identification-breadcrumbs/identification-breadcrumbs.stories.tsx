import { ComponentMeta } from '@storybook/react'
import { IdentificationBreadcrumbs } from './identification-breadcrumbs'

type Meta = ComponentMeta<typeof IdentificationBreadcrumbs>

export default {
  title: 'Components/Identification/IdentificationBreadcrumbs',
  component: IdentificationBreadcrumbs,
} as Meta

export const Default: Meta = {
  args: {
    nodes: [
      { id: 'erebidae', title: 'Erebidae' },
      { id: 'arctiinae', title: 'Arctiinae' },
      { id: 'lithosiini', title: 'Lithosiini' },
    ],
  },
}
