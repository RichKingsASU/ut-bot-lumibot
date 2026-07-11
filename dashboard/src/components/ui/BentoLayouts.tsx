import * as React from "react"
import { cn } from "../../lib/utils"

export const BentoGrid = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn(
      "grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 auto-rows-[minmax(180px,auto)]",
      className
    )}
    {...props}
  />
))
BentoGrid.displayName = "BentoGrid"

export interface BentoTileProps extends React.HTMLAttributes<HTMLDivElement> {
  colSpan?: 1 | 2 | 3 | 4
  rowSpan?: 1 | 2 | 3
}

export const BentoTile = React.forwardRef<HTMLDivElement, BentoTileProps>(
  ({ className, colSpan = 1, rowSpan = 1, ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={cn(
          "rounded-xl border bg-card text-card-foreground shadow-sm flex flex-col overflow-hidden relative",
          {
            "md:col-span-1": colSpan === 1,
            "md:col-span-2": colSpan === 2,
            "md:col-span-3": colSpan === 3,
            "md:col-span-4": colSpan === 4,
            "row-span-1": rowSpan === 1,
            "row-span-2": rowSpan === 2,
            "row-span-3": rowSpan === 3,
          },
          className
        )}
        {...props}
      />
    )
  }
)
BentoTile.displayName = "BentoTile"
