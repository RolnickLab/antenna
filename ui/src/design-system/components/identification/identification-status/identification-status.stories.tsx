import { ComponentMeta } from '@storybook/react'
import { IconType } from 'design-system/components/icon/icon'
import { IdentificationStatus } from './identification-status'
import { StatusTheme } from './types'

type Meta = ComponentMeta<typeof IdentificationStatus>

export default {
  title: 'Components/Identification/IdentificationStatus',
  component: IdentificationStatus,
  argTypes: {
    value: { control: { type: 'range', min: 0, max: 100, step: 1 } },
  },
} as Meta

export const Default: Meta = {
  args: {
    iconType: IconType.Identifiers,
    theme: StatusTheme.Success,
    value: 75,
  },
}
