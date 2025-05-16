import * as React from "react";
import { cn } from "@/lib/utils";

export function VisuallyHidden({
  children,
  className,
  ...props
}: React.HTMLAttributes<HTMLSpanElement>) {
  return (
    <span
      data-slot="visually-hidden"
      className={cn(
        "absolute -m-[1px] h-[1px] w-[1px] overflow-hidden border-0 p-0 whitespace-nowrap",
        className,
      )}
      {...props}
    >
      {children}
    </span>
  );
}
