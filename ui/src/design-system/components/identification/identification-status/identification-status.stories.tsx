import { ComponentMeta } from '@storybook/react'
import { IdentificationStatus } from './identification-status'

type Meta = ComponentMeta<typeof IdentificationStatus>

export default {
  title: 'Components/Identification/IdentificationStatus',
  component: IdentificationStatus,
  argTypes: {
    alertThreshold: { control: { type: 'range', min: 0, max: 1, step: 0.01 } },
    score: { control: { type: 'range', min: 0, max: 1, step: 0.01 } },
    warningThreshold: {
      control: { type: 'range', min: 0, max: 1, step: 0.01 },
    },
  },
} as Meta

export const Default: Meta = {
  args: {
    alertThreshold: 0.6,
    isVerified: false,
    score: 0.9,
    warningThreshold: 0.8,
  },
}

export const Verified: Meta = {
  args: {
    alertThreshold: 0.6,
    isVerified: true,
    score: 1.0,
    warningThreshold: 0.6,
  },
}

export const BelowWarningThreshold: Meta = {
  args: {
    alertThreshold: 0.6,
    isVerified: false,
    score: 0.7,
    warningThreshold: 0.8,
  },
}

export const BelowAlertThreshold: Meta = {
  args: {
    alertThreshold: 0.6,
    isVerified: false,
    score: 0.5,
    warningThreshold: 0.8,
  },
}
