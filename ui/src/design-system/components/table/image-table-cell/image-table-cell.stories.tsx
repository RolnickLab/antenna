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
      {
        src: 'https://placekitten.com/240/200',
      },
      {
        src: 'https://placekitten.com/200/240',
      },
      {
        src: 'https://placekitten.com/260/260',
      },
      {
        src: 'https://placekitten.com/260/160',
      },
      {
        src: 'https://placekitten.com/160/260',
      },
      {
        src: 'https://placekitten.com/260/200',
      },
      {
        src: 'https://placekitten.com/200/260',
      },
    ],
    theme: ImageCellTheme.Default,
  },
}
