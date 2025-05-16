"use client";

import { useEffect, useState, useCallback, useMemo } from "react";
import {
  FieldDistribution,
  FieldHarmonizationMapping,
  CreateMappingPayload,
  UpdateMappingPayload,
  FieldType,
  FieldEmbeddingsUmapResponse,
  HarmonizationSuggestion,
  UmapFieldData,
  useFieldEmbeddingsUmap,
  useFieldDistribution,
  useFieldMappings,
  useActiveFieldMapping,
  useSuggestFieldMappingsMutation,
  useCreateFieldMappingMutation,
  useUpdateFieldMappingMutation,
  useDeleteFieldMappingMutation,
  useApplyMappingsRetroactivelyMutation,
} from "@/lib/api/admin/field-harmonization";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Card } from "@/components/ui/card";
import LoadingSpinner from "@/components/ui/loading-spinner";
import { Title } from "@/components/ui/text/Title";

// Deck.gl Imports
import {
  OrbitViewState,
  LightingEffect,
  AmbientLight,
  _SunLight as SunLight,
} from "@deck.gl/core";

// Import Tab Components
import OverviewTab from "./OverviewTab";
import DistributionTab from "./DistributionTab";
import SuggestionsTab from "./SuggestionsTab";
import MappingsTab from "./MappingsTab";

// Types (Imports are likely still needed once api-client exports them)
// Assume FieldType is available globally or imported elsewhere for now
type BadgeVariant = "default" | "neutral" | "success" | "error" | "warning";

// Helper function to map FieldType to BadgeVariant (Restored)
const getColorForType = (type: FieldType): BadgeVariant => {
  switch (type) {
    case "numeric":
      return "default"; // Map to blue
    case "categorical":
      return "neutral"; // Map to gray
    case "boolean":
      return "warning"; // Map to yellow
    case "text":
      return "default"; // Map to blue
    case "mixed":
      return "error"; // Map to red
    case "unknown":
      return "neutral"; // Map to gray
  }
};

export interface FieldCluster {
  id: string;
  canonical_field: string;
  similar_fields: string[];
  field_types: Record<string, FieldType>;
  similarity_scores: Record<string, number>;
  patterns: Record<string, any | null>;
  suggested_name?: string;
}

// Main Component
export default function FieldHarmonizationPage() {
  const [activeTab, setActiveTab] = useState("overview");
  const [suggestionThreshold, setSuggestionThreshold] = useState(0.75);
  const [selectedClusterId, setSelectedClusterId] = useState<string | null>(
    null,
  );
  const [umapViewState, setUmapViewState] = useState<OrbitViewState>({
    target: [0, 0, 0],
    rotationX: 30,
    rotationOrbit: -30,
    zoom: 0,
    minZoom: -5,
    maxZoom: 10,
  });

  // --- React Query Data Fetching ---
  const {
    data: fieldsData,
    isLoading: isLoadingFields,
    isError: isErrorFields,
    error: fieldsErrorData,
  } = useFieldDistribution();
  const fields: FieldDistribution[] = fieldsData || [];

  const {
    data: mappingsData,
    isLoading: isLoadingMappings,
    isError: isErrorMappings,
    error: mappingsErrorData,
  } = useFieldMappings();
  const mappings: FieldHarmonizationMapping[] = mappingsData || [];

  const {
    data: activeMappingsData,
    isLoading: isLoadingActiveMappings,
    isError: isErrorActiveMappings,
    error: activeMappingsErrorData,
  } = useActiveFieldMapping();
  const activeMappings: FieldHarmonizationMapping[] = activeMappingsData || [];

  const umapQueryNComponents = 3;
  const {
    data: umapData,
    isLoading: isUmapLoading,
    isError: isUmapError,
    error: umapErrorData,
    refetch: refetchUmapData,
  } = useFieldEmbeddingsUmap(undefined, 5, 0.1, umapQueryNComponents, "cosine");

  // Combined loading and error states for initial page view
  const isLoadingPageData =
    isLoadingFields || isLoadingMappings || isLoadingActiveMappings; // isUmapLoading is separate for its section
  const pageError =
    fieldsErrorData || mappingsErrorData || activeMappingsErrorData;

  // useEffect to recalculate umapViewState when umapData changes (from hook)
  useEffect(() => {
    if (umapData && umapData.fields.length > 0) {
      const coords = umapData.fields.map((f: UmapFieldData) => f.coordinates);
      const coords3D: [number, number, number][] = coords.map(
        (c: UmapFieldData["coordinates"]) =>
          c.length === 2 ? [c[0], c[1], 0] : (c as [number, number, number]),
      );
      const xs = coords3D.map((c) => c[0]);
      const ys = coords3D.map((c) => c[1]);
      const zs = coords3D.map((c) => c[2]);
      const min_x = Math.min(...xs);
      const max_x = Math.max(...xs);
      const min_y = Math.min(...ys);
      const max_y = Math.max(...ys);
      const min_z = Math.min(...zs);
      const max_z = Math.max(...zs);
      const center_x = (min_x + max_x) / 2;
      const center_y = (min_y + max_y) / 2;
      const center_z = (min_z + max_z) / 2;
      const maxExtent = Math.max(max_x - min_x, max_y - min_y, max_z - min_z);
      let calculatedZoom = 5 - Math.log2(Math.max(1, maxExtent));
      calculatedZoom = Math.max(
        umapViewState.minZoom ?? -5,
        Math.min(umapViewState.maxZoom ?? 10, calculatedZoom),
      );
      setUmapViewState((vs) => ({
        ...vs,
        target: [center_x, center_y, center_z],
        zoom: calculatedZoom,
      }));
    }
  }, [umapData]);

  // --- Mutations ---
  const suggestMappingsMutation = useSuggestFieldMappingsMutation();
  const createMappingMutation = useCreateFieldMappingMutation();
  const updateMappingMutation = useUpdateFieldMappingMutation();
  const deleteMappingMutation = useDeleteFieldMappingMutation();
  const applyRetroactiveMutation = useApplyMappingsRetroactivelyMutation();

  const suggestionsDataFromMutation: HarmonizationSuggestion | null =
    suggestMappingsMutation.data || null;
  const currentSuggestions = useMemo(
    () => suggestionsDataFromMutation?.clusters || [],
    [suggestionsDataFromMutation],
  );

  const generateSuggestions = useCallback(async () => {
    setSelectedClusterId(null); // Reset selected cluster
    try {
      await suggestMappingsMutation.mutateAsync({
        similarity_threshold: suggestionThreshold,
        min_occurrence: 5, // Or make this configurable
      });
    } catch (err) {
      console.error(
        "Error caught in generateSuggestions component callback:",
        err,
      );
    }
  }, [suggestMappingsMutation, suggestionThreshold]);

  const handleClusterSelectById = (clusterId: string | null) => {
    setSelectedClusterId(clusterId);
  };
  const handleClusterSelectByName = (canonicalFieldName: string) => {
    const cluster = currentSuggestions.find(
      (c) =>
        c.canonical_field === canonicalFieldName ||
        c.suggested_name === canonicalFieldName,
    );
    if (cluster) {
      setSelectedClusterId(cluster.id);
      setActiveTab("suggestions");
    }
  };

  // --- Mapping CUD (To be refactored with mutations) ---
  const handleCreateMapping = useCallback(
    async (
      newMappingData: Omit<CreateMappingPayload, "created_by">,
    ): Promise<FieldHarmonizationMapping | null> => {
      try {
        const createdMapping =
          await createMappingMutation.mutateAsync(newMappingData);
        return createdMapping || null;
      } catch (err) {
        console.error(
          "Error caught in handleCreateMapping component callback:",
          err,
        );
        return null;
      }
    },
    [createMappingMutation],
  );

  const handleUpdateMapping = useCallback(
    async (
      mappingId: string,
      payload: UpdateMappingPayload,
    ): Promise<FieldHarmonizationMapping | null> => {
      try {
        const updated = await updateMappingMutation.mutateAsync({
          mappingId,
          updates: payload,
        });
        return updated || null;
      } catch (err) {
        console.error("Error in handleUpdateMapping:", err);
        return null;
      }
    },
    [updateMappingMutation],
  );

  const handleDeleteMapping = useCallback(
    async (mappingId: string): Promise<void> => {
      try {
        await deleteMappingMutation.mutateAsync(mappingId);
      } catch (err) {
        console.error("Error in handleDeleteMapping:", err);
      }
    },
    [deleteMappingMutation],
  );

  const handleActivateMapping = useCallback(
    async (
      mappingId: string,
      activate: boolean,
    ): Promise<FieldHarmonizationMapping | null> => {
      try {
        const result = await updateMappingMutation.mutateAsync({
          mappingId,
          updates: { is_active: activate },
        });
        return result || null;
      } catch (err) {
        console.error("Error in handleActivateMapping:", err);
        return null;
      }
    },
    [updateMappingMutation],
  );

  const handleApplyRetroactive = useCallback(
    async (
      mappingId: string,
    ): Promise<{
      message: string;
      processed_count: number;
      total_updated: number;
    } | null> => {
      try {
        const result = await applyRetroactiveMutation.mutateAsync(undefined);
        return result || null;
      } catch (err) {
        console.error("Error in handleApplyRetroactive:", err);
        return null;
      }
    },
    [applyRetroactiveMutation],
  );

  // --- Deck.gl Layer Configuration --- //
  const lightingEffect = useMemo(() => {
    const ambientLight = new AmbientLight({
      color: [255, 255, 255],
      intensity: 1.0,
    });
    const sunLight = new SunLight({
      timestamp: Date.now(),
      color: [255, 255, 255],
      intensity: 2.0,
    });
    return new LightingEffect({ ambientLight, sunLight });
  }, []);

  // Helper specifically for Mesh Layer Color (RGB Array)
  const typeColorMapping: Record<FieldType, [number, number, number]> = useMemo(
    () => ({
      numeric: [0, 128, 255],
      categorical: [128, 128, 128],
      boolean: [255, 191, 0],
      text: [0, 128, 255],
      mixed: [255, 0, 0],
      unknown: [128, 128, 128],
    }),
    [],
  );

  // --- Render Logic --- //
  if (isLoadingPageData) {
    return (
      <div className="flex h-screen items-center justify-center">
        <LoadingSpinner /> <p className="ml-2">Loading harmonization data...</p>
      </div>
    );
  }

  // Display a global error banner if needed
  const renderError = () => {
    const errorToDisplay =
      pageError ||
      umapErrorData ||
      suggestMappingsMutation.error ||
      createMappingMutation.error ||
      updateMappingMutation.error ||
      deleteMappingMutation.error ||
      applyRetroactiveMutation.error;
    if (!errorToDisplay) return null;
    return (
      <Card className="mb-4 p-4 text-red-600">
        <p>
          <strong>Error:</strong>{" "}
          {(errorToDisplay as any)?.message || "An unexpected error occurred."}
        </p>
      </Card>
    );
  };

  return (
    <div className="container mx-auto p-4">
      <Title className="mb-6 text-2xl font-bold">
        Field Harmonization Dashboard
      </Title>
      {renderError()}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="grid w-full grid-cols-2 md:grid-cols-4">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="distribution">Distribution & UMAP</TabsTrigger>
          <TabsTrigger value="suggestions">Suggestions</TabsTrigger>
          <TabsTrigger value="mappings">Mappings</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="mt-4">
          <OverviewTab
            fields={fields}
            activeMappings={activeMappings}
            isLoading={isLoadingPageData}
            error={pageError ? (pageError as Error).message : null}
            onSelectCanonicalField={handleClusterSelectByName}
            umapData={umapData || null}
            isUmapLoading={isUmapLoading}
            umapError={umapErrorData ? (umapErrorData as Error).message : null}
            umapViewState={umapViewState}
            onUmapViewStateChange={setUmapViewState}
            onRefetchUmap={refetchUmapData}
          />
        </TabsContent>

        <TabsContent value="distribution" className="mt-4">
          <DistributionTab
            fields={fields}
            isLoading={isLoadingFields}
            error={fieldsErrorData ? (fieldsErrorData as Error).message : null}
            getColorForType={getColorForType}
            selectedClusterId={selectedClusterId}
            suggestions={currentSuggestions}
            umapData={umapData || null}
            isUmapLoading={isUmapLoading}
            umapError={umapErrorData ? (umapErrorData as Error).message : null}
            umapViewState={umapViewState}
            onUmapViewStateChange={setUmapViewState}
            onRefetchUmap={refetchUmapData}
          />
        </TabsContent>

        <TabsContent value="suggestions" className="mt-4">
          <SuggestionsTab
            suggestions={currentSuggestions}
            isLoading={suggestMappingsMutation.isPending}
            error={
              suggestMappingsMutation.error
                ? (suggestMappingsMutation.error as Error).message
                : null
            }
            onGenerateSuggestions={generateSuggestions}
            suggestionThreshold={suggestionThreshold}
            onSetSuggestionThreshold={setSuggestionThreshold}
            selectedClusterId={selectedClusterId}
            onSelectCluster={handleClusterSelectById}
            onCreateMapping={handleCreateMapping}
            isSubmitting={createMappingMutation.isPending}
            fields={fields}
          />
        </TabsContent>

        <TabsContent value="mappings" className="mt-4">
          <MappingsTab
            mappings={mappings}
            activeMappings={activeMappings}
            isLoading={isLoadingMappings || isLoadingActiveMappings}
            error={
              mappingsErrorData || activeMappingsErrorData
                ? ((mappingsErrorData || activeMappingsErrorData) as Error)
                    ?.message
                : null
            }
            onCreateMapping={handleCreateMapping}
            fields={fields}
            isCreating={createMappingMutation.isPending}
            onUpdateMapping={handleUpdateMapping}
            isUpdating={updateMappingMutation.isPending}
            onDeleteMapping={handleDeleteMapping}
            isDeleting={deleteMappingMutation.isPending}
            onActivateMapping={handleActivateMapping}
            isActivating={updateMappingMutation.isPending}
            onApplyRetroactive={handleApplyRetroactive}
            isApplyingRetroactive={applyRetroactiveMutation.isPending}
          />
        </TabsContent>
      </Tabs>
    </div>
  );
}
