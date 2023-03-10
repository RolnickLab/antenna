import { ComponentMeta } from '@storybook/react'
import {
  Checkbox,
  CheckboxTheme,
} from 'design-system/components/checkbox/checkbox'
import { TableCell } from './table-cell'

type Meta = ComponentMeta<typeof TableCell>

export default {
  title: 'Components/Table/TableCell',
  component: TableCell,
  argTypes: {
    children: {
      control: { type: 'disable' },
    },
  },
} as Meta

export const WithOneRow: Meta = {
  args: {
    title: 'Lorem ipsum',
    text: ['Lorem ipsum dolor sit amet'],
  },
}

export const WithTwoRows: Meta = {
  args: {
    title: 'Lorem ipsum',
    text: ['Lorem ipsum dolor sit amet', 'Lorem ipsum dolor sit amet'],
  },
}

export const WithCheckbox: Meta = {
  args: {
    title: 'Lorem ipsum',
    text: ['Lorem ipsum dolor sit amet'],
    children: (
      <Checkbox id="checkbox-default" label="Lorem ipsum" defaultChecked />
    ),
  },
}

export const WithSuccessCheckbox: Meta = {
  args: {
    title: 'Lorem ipsum',
    text: ['Lorem ipsum dolor sit amet'],
    children: (
      <Checkbox
        id="checkbox-success"
        label="Lorem ipsum"
        theme={CheckboxTheme.Success}
        defaultChecked
      />
    ),
  },
}

export const WithAlertCheckbox: Meta = {
  args: {
    title: 'Lorem ipsum',
    text: ['Lorem ipsum dolor sit amet'],
    children: (
      <Checkbox
        id="checkbox-alert"
        label="Lorem ipsum"
        theme={CheckboxTheme.Alert}
        defaultChecked
      />
    ),
  },
}
