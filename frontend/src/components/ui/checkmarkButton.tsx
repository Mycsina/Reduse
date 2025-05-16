import React from "react";
import { CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button"; // Assuming Button component exists
import { cn } from "@/lib/utils"; // Assuming cn utility exists

interface FavoriteButtonProps {
  isFavorite: boolean;
  onClick: () => void;
  className?: string;
  size?: "default" | "sm" | "lg" | "icon";
  disabled?: boolean;
}

const FavoriteButton: React.FC<FavoriteButtonProps> = ({
  isFavorite,
  onClick,
  className,
  size = "icon",
  disabled,
}) => {
  return (
    <Button
      variant="outline"
      size={size}
      onClick={onClick}
      className={cn(
        "text-muted-foreground hover:text-primary",
        disabled && "hover:text-muted-foreground cursor-not-allowed opacity-50",
        className,
      )}
      aria-label={isFavorite ? "Remove from favorites" : "Add to favorites"}
      disabled={disabled}
    >
      <CheckCircle2
        className={cn(
          "h-4 w-4",
          isFavorite && !disabled && "animate-pulse text-green-600",
        )}
      />
    </Button>
  );
};

export default FavoriteButton;
