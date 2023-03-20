import { ComponentMeta } from '@storybook/react'
import { CellTheme } from '../types'
import { BasicTableCell } from './basic-table-cell'

type Meta = ComponentMeta<typeof BasicTableCell>

export default {
  title: 'Components/Table/BasicTableCell',
  component: BasicTableCell,
} as Meta

export const WithText: Meta = {
  args: {
    value: 'Lorem ipsum',
    theme: CellTheme.Primary,
  },
}

export const WithNumber: Meta = {
  args: {
    value: 1234,
    theme: CellTheme.Default,
  },
}

export const WithDetails: Meta = {
  args: {
    value: 'Lorem ipsum',
    details: ['Lorem ipsum dolor sit amet'],
    theme: CellTheme.Primary,
  },
}
