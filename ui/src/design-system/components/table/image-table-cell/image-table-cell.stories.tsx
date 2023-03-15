import { ComponentMeta } from '@storybook/react'
import { ImageCellTheme } from '../types'
import { ImageTableCell } from './image-table-cell'

type Meta = ComponentMeta<typeof ImageTableCell>

export default {
  title: 'Components/Table/ImageTableCell',
  component: ImageTableCell,
} as Meta

export const WithOneImage: Meta = {
  args: {
    images: [
      {
        src: 'https://placekitten.com/240/240',
      },
    ],
    theme: ImageCellTheme.Default,
  },
}

export const WithManyImages: Meta = {
  args: {
    images: [
      {
        src: 'https://placekitten.com/240/240',
      },
      {
        src: 'https://placekitten.com/240/160',
      },
      {
        src: 'https://placekitten.com/160/240',
      },
    ],
    theme: ImageCellTheme.Default,
  },
}
