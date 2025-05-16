import React from "react";
import { cn } from "@/lib/utils";

interface GridProps extends React.HTMLAttributes<HTMLDivElement> {
  numItems?: number;
  numItemsSm?: number;
  numItemsMd?: number;
  numItemsLg?: number;
}

function Grid({
  children,
  className,
  numItems = 1,
  numItemsSm,
  numItemsMd,
  numItemsLg,
  ...props
}: GridProps) {
  const gridCols = `grid-cols-${numItems}`;
  const smGridCols = numItemsSm ? `sm:grid-cols-${numItemsSm}` : "";
  const mdGridCols = numItemsMd ? `md:grid-cols-${numItemsMd}` : "";
  const lgGridCols = numItemsLg ? `lg:grid-cols-${numItemsLg}` : "";

  return (
    <div
      data-slot="grid"
      className={cn(
        "grid",
        gridCols,
        smGridCols,
        mdGridCols,
        lgGridCols,
        className,
      )}
      {...props}
    >
      {children}
    </div>
  );
}

export { Grid };
