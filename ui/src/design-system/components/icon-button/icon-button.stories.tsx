import { ComponentMeta } from '@storybook/react'
import { IconType } from '../icon/icon'
import { IconButton, IconButtonShape, IconButtonTheme } from './icon-button'

type Meta = ComponentMeta<typeof IconButton>

export default {
  title: 'Components/Buttons/IconButton',
  component: IconButton,
} as Meta

export const Default: Meta = {
  args: {
    icon: IconType.Checkmark,
    shape: IconButtonShape.Square,
    theme: IconButtonTheme.Default,
  },
}

export const WithRoundShape: Meta = {
  args: {
    ...Default.args,
    shape: IconButtonShape.Round,
  },
}

export const WithNeutralTheme: Meta = {
  args: {
    ...Default.args,
    theme: IconButtonTheme.Neutral,
  },
}

export const WithSuccessTheme: Meta = {
  args: {
    ...Default.args,
    theme: IconButtonTheme.Success,
  },
}
