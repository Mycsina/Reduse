import React from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import LoadingSpinner from "@/components/ui/loading-spinner";
import {
  FieldDistribution,
  FieldHarmonizationMapping,
  FieldEmbeddingsUmapResponse,
  useInvalidateFieldEmbeddingsMutation,
} from "@/lib/api/admin/field-harmonization";
import { DonutChart } from "@/components/ui/charts/donutChart";
import { OrbitViewState } from "@deck.gl/core";

interface OverviewTabProps {
  fields: FieldDistribution[];
  activeMappings: FieldHarmonizationMapping[];
  isLoading: boolean;
  error: string | null;
  umapData: FieldEmbeddingsUmapResponse | null;
  isUmapLoading: boolean;
  umapError: string | null;
  umapViewState: OrbitViewState;
  onUmapViewStateChange: (viewState: OrbitViewState) => void;
  onRefetchUmap: () => void;
  onSelectCanonicalField: (fieldName: string) => void;
}

const OverviewTab: React.FC<OverviewTabProps> = ({
  fields,
  activeMappings,
  isLoading,
  error,
  umapData,
  isUmapLoading,
  umapError,
  umapViewState,
  onUmapViewStateChange,
  onRefetchUmap,
  onSelectCanonicalField,
}) => {
  const invalidateEmbeddingsMutation = useInvalidateFieldEmbeddingsMutation();

  const handleInvalidateEmbeddings = async () => {
    try {
      await invalidateEmbeddingsMutation.mutateAsync();
    } catch (err) {
      console.error("Error invalidating embeddings from OverviewTab:", err);
    }
  };

  const getFieldTypeDistribution = () => {
    const typeCounts: Record<string, number> = {};
    fields.forEach((field) => {
      typeCounts[field.field_type] = (typeCounts[field.field_type] || 0) + 1;
    });

    return Object.entries(typeCounts).map(([type, count]) => ({
      type: type.charAt(0).toUpperCase() + type.slice(1),
      count: count,
    }));
  };

  if (isLoading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <LoadingSpinner />
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded border border-red-500 bg-red-100 p-4 text-red-700">
        <p>{error}</p>
      </div>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardDescription>
          Summary of field harmonization status.
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            {/* <CardTitle>Total Fields Analyzed</CardTitle> */}
          </CardHeader>
          <CardContent>
            <p className="text-tremor-default text-tremor-content dark:text-dark-tremor-content">
              Total Fields Analyzed: {fields.length}
            </p>
            <p className="text-tremor-default text-tremor-content-subtle dark:text-dark-tremor-content-subtle text-xs">
              Fields found across all listings.
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>{/* <CardTitle>Active Mapping</CardTitle> */}</CardHeader>
          <CardContent>
            {activeMappings && activeMappings.length > 0 ? (
              <div>
                <p className="text-tremor-content dark:text-dark-tremor-content font-medium">
                  Active Mapping: {activeMappings[0].name} (ID:{" "}
                  {activeMappings[0]._id})
                </p>
              </div>
            ) : (
              <p className="text-tremor-default text-tremor-content-subtle dark:text-dark-tremor-content-subtle">
                No active mapping set.
              </p>
            )}
          </CardContent>
        </Card>
        <Card className="md:col-span-2">
          <CardHeader>
            <CardDescription>Field Type Distribution</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex h-[250px] items-center justify-center">
              <DonutChart
                data={getFieldTypeDistribution()}
                category="type"
                value="count"
                showLabel={true}
                className="h-48 w-48"
              />
            </div>
          </CardContent>
        </Card>
        <Card className="md:col-span-2">
          <CardHeader>
            <CardDescription>
              Manage stored field embeddings used for visualization.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button
              onClick={handleInvalidateEmbeddings}
              disabled={invalidateEmbeddingsMutation.isPending}
              variant="destructive"
              size="sm"
            >
              {invalidateEmbeddingsMutation.isPending ? (
                <LoadingSpinner className="mr-2 h-4 w-4 animate-spin" />
              ) : null}
              Invalidate All Embeddings
            </Button>
            <p className="text-muted-foreground mt-2 text-xs">
              This deletes stored embeddings. They will be recalculated
              automatically when needed.
            </p>
          </CardContent>
        </Card>
      </CardContent>
    </Card>
  );
};

export default OverviewTab;
