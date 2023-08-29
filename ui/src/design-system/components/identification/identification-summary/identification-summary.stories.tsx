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
      username: 'Andre Poremski',
      profileImage: 'https://placekitten.com/600/400',
    },
    result: { id: 'lycomorphodes-sordida', title: 'Lycomorphodes sordida' },
    nodes: [
      { id: 'erebidae', title: 'Erebidae' },
      { id: 'arctiinae', title: 'Arctiinae' },
      { id: 'lithosiini', title: 'Lithosiini' },
    ],
  },
}

export const WithoutProfileImage: Meta = {
  args: {
    user: {
      username: 'Andre Poremski',
    },
    result: { id: 'lycomorphodes-sordida', title: 'Lycomorphodes sordida' },
    nodes: [
      { id: 'erebidae', title: 'Erebidae' },
      { id: 'arctiinae', title: 'Arctiinae' },
      { id: 'lithosiini', title: 'Lithosiini' },
    ],
  },
}

export const Overridden: Meta = {
  args: {
    user: {
      username: 'Andre Poremski',
      profileImage: 'https://placekitten.com/600/400',
    },
    result: {
      id: 'lycomorphodes-sordida',
      title: 'Lycomorphodes sordida',
      overridden: true,
    },
    nodes: [
      { id: 'erebidae', title: 'Erebidae' },
      { id: 'arctiinae', title: 'Arctiinae' },
      { id: 'lithosiini', title: 'Lithosiini' },
    ],
  },
}

export const ByMachine: Meta = {
  args: {
    result: { id: 'lycomorphodes-sordida', title: 'Lycomorphodes sordida' },
    nodes: [
      { id: 'erebidae', title: 'Erebidae' },
      { id: 'arctiinae', title: 'Arctiinae' },
      { id: 'lithosiini', title: 'Lithosiini' },
    ],
  },
}
