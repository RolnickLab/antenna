import { ComponentMeta } from '@storybook/react'
import { IdentificationStatus } from './identification-status'

type Meta = ComponentMeta<typeof IdentificationStatus>

export default {
  title: 'Components/Identification/IdentificationStatus',
  component: IdentificationStatus,
  argTypes: {
    score: { control: { type: 'range', min: 0, max: 1, step: 0.01 } },
    scoreThreshold: { control: { type: 'range', min: 0, max: 1, step: 0.01 } },
  },
} as Meta

export const Default: Meta = {
  args: {
    alertThreshold: 0.6,
    isVerified: false,
    score: 0.7,
    warningThreshold: 0.9,
  },
}

export const Verified: Meta = {
  args: {
    isVerified: true,
    score: 0.7,
    warningThreshold: 0.6,
  },
}

export const BelowThreshold: Meta = {
  args: {
    alertThreshold: 0.6,
    isVerified: false,
    score: 0.5,
    warningThreshold: 0.9,
  },
}
