import { cn } from "@/lib/utils";

export function LoadingDots({ className }: { className?: string }) {
  return (
    <div className={cn("flex items-center space-x-1", className)}>
      {[0, 1, 2].map((i) => (
        <div
          key={i}
          className={cn(
            "h-1.5 w-1.5 rounded-full bg-current",
            "animate-bounce duration-1000",
            i === 0 && "delay-0",
            i === 1 && "delay-150",
            i === 2 && "delay-300"
          )}
          style={{
            animationDuration: "1000ms",
          }}
        />
      ))}
    </div>
  );
}
