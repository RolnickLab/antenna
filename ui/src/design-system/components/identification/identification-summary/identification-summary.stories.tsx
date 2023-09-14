import { ComponentMeta } from '@storybook/react'
import { IdentificationSummary } from './identification-summary'

type Meta = ComponentMeta<typeof IdentificationSummary>

const EXAMPLE_RANKS = [
  { id: 'erebidae', name: 'Erebidae', rank: 'Family' },
  { id: 'arctiinae', name: 'Arctiinae', rank: 'Genus' },
  { id: 'lithosiini', name: 'Lithosiini', rank: 'Species' },
]

export default {
  title: 'Components/Identification/IdentificationSummary',
  component: IdentificationSummary,
} as Meta

export const Default: Meta = {
  args: {
    identification: {
      id: 'lycomorphodes-sordida',
      name: 'Lycomorphodes sordida',
    },
    ranks: EXAMPLE_RANKS,
    user: {
      name: 'Andre Poremski',
      image: 'https://placekitten.com/600/400',
    },
  },
}

export const WithoutProfileImage: Meta = {
  args: {
    identification: {
      id: 'lycomorphodes-sordida',
      name: 'Lycomorphodes sordida',
    },
    ranks: EXAMPLE_RANKS,
    user: {
      name: 'Andre Poremski',
    },
  },
}

export const Overridden: Meta = {
  args: {
    identification: {
      id: 'lycomorphodes-sordida',
      name: 'Lycomorphodes sordida',
      overridden: true,
    },
    ranks: EXAMPLE_RANKS,
    user: {
      name: 'Andre Poremski',
      image: 'https://placekitten.com/600/400',
    },
  },
}

export const ByMachine: Meta = {
  args: {
    identification: {
      id: 'lycomorphodes-sordida',
      name: 'Lycomorphodes sordida',
    },
    ranks: EXAMPLE_RANKS,
  },
}
