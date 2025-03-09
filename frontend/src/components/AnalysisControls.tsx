"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { apiClient } from "@/lib/api-client";
import { toast } from "@/hooks/use-toast";

export default function AnalysisControls() {
  const [isLoading, setIsLoading] = useState(false);
  const router = useRouter();

  const handleAction = async (
    action: () => Promise<any>,
    successMessage: string
  ) => {
    try {
      setIsLoading(true);
      await action();
      toast({ title: successMessage });
      router.refresh();
    } catch (error) {
      toast({
        title: "Operation failed",
        description:
          error instanceof Error ? error.message : "Unknown error occurred",
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {/* Start Analysis */}
      <Button
        onClick={() =>
          handleAction(
            () => apiClient.startAnalysis(),
            "Started analysis of pending listings"
          )
        }
        disabled={isLoading}
      >
        Start Analysis
      </Button>

      {/* Resume Analysis */}
      <Button
        onClick={() =>
          handleAction(
            () => apiClient.resumeAnalysis(),
            "Resumed in-progress analyses"
          )
        }
        variant="secondary"
        disabled={isLoading}
      >
        Resume Analysis
      </Button>

      {/* Retry Failed */}
      <Button
        onClick={() =>
          handleAction(
            () => apiClient.retryFailedAnalyses(),
            "Retrying failed analyses"
          )
        }
        variant="secondary"
        disabled={isLoading}
      >
        Retry Failed
      </Button>

      {/* Reanalyze All */}
      <Button
        onClick={() =>
          handleAction(
            () => apiClient.reanalyzeListings(),
            "Started reanalyzing all listings"
          )
        }
        variant="secondary"
        disabled={isLoading}
      >
        Reanalyze All
      </Button>

      {/* Regenerate Embeddings */}
      <Button
        onClick={() =>
          handleAction(
            () => apiClient.regenerateEmbeddings(),
            "Started regenerating embeddings"
          )
        }
        variant="secondary"
        disabled={isLoading}
      >
        Regenerate Embeddings
      </Button>

      {/* Cancel Analysis */}
      <Button
        onClick={() =>
          handleAction(
            () => apiClient.cancelAnalysis(),
            "Cancelled in-progress analyses"
          )
        }
        variant="destructive"
        disabled={isLoading}
      >
        Cancel All
      </Button>
    </div>
  );
}
