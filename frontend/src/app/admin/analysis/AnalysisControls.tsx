"use client";

import { Button } from "@/components/ui/button";

import {
  useStartAnalysisMutation,
  useResumeAnalysisMutation,
  useRetryFailedAnalysesMutation,
  useRegenerateEmbeddingsMutation,
  useCancelAnalysisMutation,
} from "@/lib/api/admin/analysis";

export default function AnalysisControls() {
  const startAnalysisMutation = useStartAnalysisMutation();
  const resumeAnalysisMutation = useResumeAnalysisMutation();
  const retryFailedAnalysesMutation = useRetryFailedAnalysesMutation();
  const regenerateEmbeddingsMutation = useRegenerateEmbeddingsMutation();
  const cancelAnalysisMutation = useCancelAnalysisMutation();

  const isAnyOperationLoading =
    startAnalysisMutation.isPending ||
    resumeAnalysisMutation.isPending ||
    retryFailedAnalysesMutation.isPending ||
    regenerateEmbeddingsMutation.isPending ||
    cancelAnalysisMutation.isPending;

  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
      {/* Start Analysis */}
      <Button
        onClick={() => startAnalysisMutation.mutateAsync()}
        disabled={isAnyOperationLoading}
      >
        {startAnalysisMutation.isPending ? "Starting..." : "Start Analysis"}
      </Button>

      {/* Resume Analysis */}
      <Button
        onClick={() => resumeAnalysisMutation.mutateAsync()}
        variant="secondary"
        disabled={isAnyOperationLoading}
      >
        {resumeAnalysisMutation.isPending ? "Resuming..." : "Resume Analysis"}
      </Button>

      {/* Retry Failed */}
      <Button
        onClick={() => retryFailedAnalysesMutation.mutateAsync()}
        variant="secondary"
        disabled={isAnyOperationLoading}
      >
        {retryFailedAnalysesMutation.isPending ? "Retrying..." : "Retry Failed"}
      </Button>

      {/* Regenerate Embeddings */}
      <Button
        onClick={() => regenerateEmbeddingsMutation.mutateAsync()}
        variant="secondary"
        disabled={isAnyOperationLoading}
      >
        {regenerateEmbeddingsMutation.isPending
          ? "Regenerating..."
          : "Regenerate Embeddings"}
      </Button>

      {/* Cancel Analysis */}
      <Button
        onClick={() => cancelAnalysisMutation.mutateAsync()}
        variant="destructive"
        disabled={isAnyOperationLoading}
      >
        {cancelAnalysisMutation.isPending
          ? "Cancelling..."
          : "Cancel All Analyses"}
      </Button>
    </div>
  );
}
