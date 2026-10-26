export const getValueInRange = (args: {
  value: number
  min: number
  max: number
}) => Math.min(args.max, Math.max(args.min, args.value))
