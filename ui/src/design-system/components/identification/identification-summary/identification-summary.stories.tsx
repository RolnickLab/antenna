import { ComponentMeta } from '@storybook/react'
import { IdentificationSummary } from './identification-summary'

type Meta = ComponentMeta<typeof IdentificationSummary>

export default {
  title: 'Components/Identification/IdentificationSummary',
  component: IdentificationSummary,
} as Meta

export const Default: Meta = {
  args: {
    user: {
      name: 'Andre Poremski',
      image: 'https://placekitten.com/600/400',
    },
  },
}

export const WithoutProfileImage: Meta = {
  args: {
    user: {
      name: 'Andre Poremski',
    },
  },
}

export const Overridden: Meta = {
  args: {
    user: {
      name: 'Andre Poremski',
      image: 'https://placekitten.com/600/400',
    },
  },
}

export const ByMachine: Meta = {
  args: {},
}
