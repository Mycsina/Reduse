import React from "react";

import { cn } from "@/lib/utils"; // Assuming you have a utility for class names

interface TitleProps extends React.HTMLAttributes<HTMLHeadingElement> {
  level?: 1 | 2 | 3 | 4 | 5 | 6;
}

function Title({ children, className, level = 3, ...props }: TitleProps) {
  const Tag = `h${level}` as React.ElementType;
  return (
    <Tag
      data-slot="title"
      className={cn(
        "text-lg font-semibold text-gray-900 dark:text-gray-100", // Example default styling
        className,
      )}
      {...props}
    >
      {children}
    </Tag>
  );
}

export { Title };
