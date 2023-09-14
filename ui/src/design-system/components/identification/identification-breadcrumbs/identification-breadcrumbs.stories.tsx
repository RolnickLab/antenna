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
      { id: 'erebidae', name: 'Erebidae' },
      { id: 'arctiinae', name: 'Arctiinae' },
      { id: 'lithosiini', name: 'Lithosiini' },
    ],
  },
}
