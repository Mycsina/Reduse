"use client";

import {
  useAnalysisStatus,
} from "@/lib/api/admin/analysis";

export default function AnalysisStatus() {

  const {
    data: status, // Renaming data to status for consistency with original code
    isLoading,
    isError,
    error,
  } = useAnalysisStatus();

  if (isLoading) {
    return <div>Loading analysis status...</div>;
  }

  if (isError) {
    return (
      <div>
        Error fetching analysis status: {error?.message || "Unknown error"}
      </div>
    );
  }

  if (!status) {
    return <div>No analysis status data available.</div>;
  }

  return (
    <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
      <div>
        <h2 className="text-lg font-semibold">Pending</h2>
        <p className="text-2xl">{status.pending ?? 0}</p>
      </div>
      <div>
        <h2 className="text-lg font-semibold">In Progress</h2>
        <p className="text-2xl">{status.in_progress ?? 0}</p>
      </div>
      <div>
        <h2 className="text-lg font-semibold">Completed</h2>
        <p className="text-2xl">{status.completed ?? 0}</p>
      </div>
      <div>
        <h2 className="text-lg font-semibold">Failed</h2>
        <p className="text-2xl">{status.failed ?? 0}</p>
      </div>
    </div>
  );
}
