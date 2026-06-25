export const StatusBar = ({
  color,
  progress,
}: {
  color: string
  progress: number // Value in range [0,1]
}) => {
  if (progress < 0 || progress > 1) {
    throw Error(
      `Property progress has value ${progress}, but must in range [0,1].`
    )
  }

  const label = `${(progress * 100).toFixed(0)}%`

  return (
    <div className="w-full min-w-32 flex items-center gap-2">
      <div className="w-full h-2 bg-border rounded-full relative">
        <div
          className="h-2 absolute top-0 left-0 rounded-full"
          style={{
            width: `${(progress / 1) * 100}%`,
            backgroundColor: color,
            transition: 'width 400ms ease, background-color 200ms ease',
          }}
        />
      </div>
      <span className="w-12 pt-0.5 text-right body-overline text-muted-foreground">
        {label}
      </span>
    </div>
  )
}
