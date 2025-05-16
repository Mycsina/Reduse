import React from "react";
import { cn } from "@/lib/utils"; // Assuming you have a utility for class names

type MetricProps = React.HTMLAttributes<HTMLDivElement>

function Metric({ children, className, ...props }: MetricProps) {
  return (
    <div
      data-slot="metric"
      className={cn(
        "text-2xl font-bold text-gray-900 dark:text-gray-100", // Switched to double quotes
        className,
      )}
      {...props}
    >
      {children}
    </div>
  );
}

export { Metric };
