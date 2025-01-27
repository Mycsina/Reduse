"use client";

import { useState, useEffect } from "react";
import { apiClient } from "@/lib/api-client";

interface AnalysisStatusData {
  pending: number;
  in_progress: number;
  completed: number;
  failed: number;
}

export default function AnalysisStatus() {
  const [status, setStatus] = useState<AnalysisStatusData | null>(null);

  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const data = await apiClient.getAnalysisStatus();
        setStatus(data);
      } catch (error) {
        console.error("Failed to fetch analysis status:", error);
      }
    };

    fetchStatus();
  }, []);

  if (!status) {
    return <div>Loading status...</div>;
  }

  return (
    <div className="grid grid-cols-2 gap-4">
      <div>
        <h2 className="text-lg font-semibold">Pending</h2>
        <p className="text-2xl">{status.pending}</p>
      </div>
      <div>
        <h2 className="text-lg font-semibold">In Progress</h2>
        <p className="text-2xl">{status.in_progress}</p>
      </div>
      <div>
        <h2 className="text-lg font-semibold">Completed</h2>
        <p className="text-2xl">{status.completed}</p>
      </div>
      <div>
        <h2 className="text-lg font-semibold">Failed</h2>
        <p className="text-2xl">{status.failed}</p>
      </div>
    </div>
  );
}
