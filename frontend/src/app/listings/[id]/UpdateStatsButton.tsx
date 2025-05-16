"use client";

import { Button } from "@/components/ui/button";
import { useUpdatePriceStatsMutation } from "@/lib/api/analytics/price-stats"; // Import the hook

export default function UpdateStatsButton() {
  const { mutateAsync: updateStats, isPending } = useUpdatePriceStatsMutation();

  const handleUpdate = async () => {
    try {
      await updateStats(); // Call the mutation
    } catch (error) {
      console.error("UpdateStatsButton: Error caught", error); // Hook will show toast
    }
  };

  return (
    <div className="mx-auto max-w-7xl px-4 py-4">
      <Button
        onClick={handleUpdate}
        disabled={isPending}
        variant="outline"
        data-update-stats
      >
        {isPending
          ? "Updating Price Statistics..."
          : "Update Price Statistics"}
      </Button>
    </div>
  );
}
