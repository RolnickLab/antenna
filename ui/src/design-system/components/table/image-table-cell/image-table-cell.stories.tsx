import { ComponentMeta } from '@storybook/react'
import { ImageCellTheme } from '../types'
import { ImageTableCell } from './image-table-cell'

type Meta = ComponentMeta<typeof ImageTableCell>

export default {
  title: 'Components/Table/ImageTableCell',
  component: ImageTableCell,
} as Meta

export const Default: Meta = {
  args: {
    image: {
      src: 'https://placekitten.com/240/240',
      alt: '',
    },
    theme: ImageCellTheme.Default,
  },
}
