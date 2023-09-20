import { ComponentMeta } from '@storybook/react'
import { Taxon } from 'data-services/models/taxa'
import { IdentificationSummary } from './identification-summary'

type Meta = ComponentMeta<typeof IdentificationSummary>

const EXAMPLE_TAXON = {
  id: 'lycomorphodes-sordida',
  name: 'Lycomorphodes sordida',
  ranks: [
    { id: 'erebidae', name: 'Erebidae', rank: 'Family' },
    { id: 'arctiinae', name: 'Arctiinae', rank: 'Genus' },
    { id: 'lithosiini', name: 'Lithosiini', rank: 'Species' },
  ],
} as Taxon

export default {
  title: 'Components/Identification/IdentificationSummary',
  component: IdentificationSummary,
} as Meta

export const Default: Meta = {
  args: {
    identification: {
      taxon: EXAMPLE_TAXON,
    },
    user: {
      name: 'Andre Poremski',
      image: 'https://placekitten.com/600/400',
    },
  },
}

export const WithoutProfileImage: Meta = {
  args: {
    identification: {
      taxon: EXAMPLE_TAXON,
    },
    user: {
      name: 'Andre Poremski',
    },
  },
}

export const Overridden: Meta = {
  args: {
    identification: {
      taxon: EXAMPLE_TAXON,
      overridden: true,
    },
    user: {
      name: 'Andre Poremski',
      image: 'https://placekitten.com/600/400',
    },
  },
}

export const ByMachine: Meta = {
  args: {
    identification: {
      taxon: EXAMPLE_TAXON,
    },
  },
}
