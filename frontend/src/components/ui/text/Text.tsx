import React from 'react';
import { cn } from '@/lib/utils'; // Assuming you have a utility for class names

type TextProps = React.HTMLAttributes<HTMLParagraphElement>

function Text({ children, className, ...props }: TextProps) {
  return (
    <p
      data-slot="text"
      className={cn(
        'text-gray-700 dark:text-gray-300', // Example default styling
        className
      )}
      {...props}
    >
      {children}
    </p>
  );
}

export { Text }; 