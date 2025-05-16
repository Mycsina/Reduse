import React from 'react';
import { Badge } from '@tremor/react';

type StatusType = 'success' | 'warning' | 'error' | 'info' | 'default';

interface StatusBadgeProps {
  status: StatusType;
  text?: string;
  className?: string;
}

const statusColors: Record<StatusType, string> = {
  success: 'green',
  warning: 'amber',
  error: 'rose',
  info: 'blue',
  default: 'gray',
};

const statusTexts: Record<StatusType, string> = {
  success: 'Success',
  warning: 'Warning',
  error: 'Error',
  info: 'Info',
  default: 'Default',
};

export default function StatusBadge({ 
  status = 'default', 
  text, 
  className = '' 
}: StatusBadgeProps) {
  const color = statusColors[status] || statusColors.default;
  const displayText = text || statusTexts[status];
  
  return (
    <Badge color={color} className={className}>
      {displayText}
    </Badge>
  );
} 