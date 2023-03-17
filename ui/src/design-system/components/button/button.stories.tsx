import { ComponentMeta } from '@storybook/react'
import { IconType } from '../icon/icon'
import { Button, ButtonTheme } from './button'

type Meta = ComponentMeta<typeof Button>

export default {
  title: 'Components/Buttons/Button',
  component: Button,
} as Meta

export const Default: Meta = {
  args: {
    label: 'Lorem ipsum',
    theme: ButtonTheme.Default,
  },
}

export const WithSuccessTheme: Meta = {
  args: {
    label: 'Lorem ipsum',
    theme: ButtonTheme.Success,
  },
}

export const WithIcon: Meta = {
  args: {
    label: 'Lorem ipsum',
    icon: IconType.Identifiers,
    theme: ButtonTheme.Default,
  },
}
