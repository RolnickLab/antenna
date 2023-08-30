import { ComponentMeta } from '@storybook/react'
import { IdentificationSummary } from './identification-summary'

type Meta = ComponentMeta<typeof IdentificationSummary>

export default {
  title: 'Components/Identification/IdentificationSummary',
  component: IdentificationSummary,
} as Meta

export const Default: Meta = {
  args: {
    identification: {
      id: 'lycomorphodes-sordida',
      title: 'Lycomorphodes sordida',
    },
    ranks: [
      { id: 'erebidae', title: 'Erebidae' },
      { id: 'arctiinae', title: 'Arctiinae' },
      { id: 'lithosiini', title: 'Lithosiini' },
    ],
    user: {
      username: 'Andre Poremski',
      profileImage: 'https://placekitten.com/600/400',
    },
  },
}

export const WithoutProfileImage: Meta = {
  args: {
    identification: {
      id: 'lycomorphodes-sordida',
      title: 'Lycomorphodes sordida',
    },
    ranks: [
      { id: 'erebidae', title: 'Erebidae' },
      { id: 'arctiinae', title: 'Arctiinae' },
      { id: 'lithosiini', title: 'Lithosiini' },
    ],
    user: {
      username: 'Andre Poremski',
    },
  },
}

export const Overridden: Meta = {
  args: {
    identification: {
      id: 'lycomorphodes-sordida',
      title: 'Lycomorphodes sordida',
      overridden: true,
    },
    ranks: [
      { id: 'erebidae', title: 'Erebidae' },
      { id: 'arctiinae', title: 'Arctiinae' },
      { id: 'lithosiini', title: 'Lithosiini' },
    ],
    user: {
      username: 'Andre Poremski',
      profileImage: 'https://placekitten.com/600/400',
    },
  },
}

export const ByMachine: Meta = {
  args: {
    identification: {
      id: 'lycomorphodes-sordida',
      title: 'Lycomorphodes sordida',
    },
    ranks: [
      { id: 'erebidae', title: 'Erebidae' },
      { id: 'arctiinae', title: 'Arctiinae' },
      { id: 'lithosiini', title: 'Lithosiini' },
    ],
  },
}
