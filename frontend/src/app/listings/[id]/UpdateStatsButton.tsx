"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { apiClient } from "@/lib/api-client";

export default function UpdateStatsButton() {
  const [isUpdating, setIsUpdating] = useState(false);

  const handleUpdate = async () => {
    try {
      setIsUpdating(true);
      const response = await apiClient.updatePriceStats();
      alert(response.message);
    } catch (error) {
      alert("Failed to update price statistics");
      console.error(error);
    } finally {
      setIsUpdating(false);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 py-4">
      <Button
        onClick={handleUpdate}
        disabled={isUpdating}
        variant="outline"
        data-update-stats
      >
        {isUpdating
          ? "Updating Price Statistics..."
          : "Update Price Statistics"}
      </Button>
    </div>
  );
}
