import React from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import LoadingSpinner from "@/components/ui/loading-spinner";
import SuggestionClusterCard from "@/components/admin/SuggestionClusterCard";
import { FieldCluster } from "./page";
import type {
  FieldDistribution,
  FieldHarmonizationMapping,
  CreateMappingPayload,
} from "@/lib/api/admin/field-harmonization";

interface SuggestionsTabProps {
  suggestions: FieldCluster[];
  isLoading: boolean;
  isSubmitting: boolean;
  error: string | null;
  suggestionThreshold: number;
  onSetSuggestionThreshold: (value: number) => void;
  selectedClusterId: string | null;
  onGenerateSuggestions: () => Promise<void>;
  onCreateMapping: (
    payload: Omit<CreateMappingPayload, "created_by">,
  ) => Promise<FieldHarmonizationMapping | null>;
  onSelectCluster: (clusterId: string | null) => void;
  fields: FieldDistribution[];
}

const SuggestionsTab: React.FC<SuggestionsTabProps> = ({
  suggestions,
  isLoading,
  isSubmitting,
  error,
  suggestionThreshold,
  onSetSuggestionThreshold,
  selectedClusterId,
  onGenerateSuggestions,
  onCreateMapping,
  onSelectCluster,
  fields,
}) => {
  const getChartData = () => {
    if (!suggestions.length) return [];
    return suggestions.map((cluster) => ({
      name: cluster.canonical_field,
      count: cluster.similar_fields.length + 1,
      isSelected: cluster.id === selectedClusterId,
    }));
  };

  const handleChartClusterSelect = (canonicalFieldName: string) => {
    const cluster = suggestions.find(
      (c) =>
        c.canonical_field === canonicalFieldName ||
        c.suggested_name === canonicalFieldName,
    );
    if (cluster) {
      onSelectCluster(cluster.id);
    }
  };

  const handleCreateMappingFromAllSuggestions = async () => {
    if (!suggestions || suggestions.length === 0) {
      console.error("No suggestions available to create a mapping from.");
      return;
    }

    const mappingItems: { original_field: string; target_field: string }[] = [];
    suggestions.forEach((cluster) => {
      const targetField = cluster.suggested_name || cluster.canonical_field;
      mappingItems.push({
        original_field: cluster.canonical_field,
        target_field: targetField,
      });
      cluster.similar_fields.forEach((similarField) => {
        mappingItems.push({
          original_field: similarField,
          target_field: targetField,
        });
      });
    });

    if (mappingItems.length === 0) {
      console.error("No valid mapping items derived from suggestions.");
      return;
    }

    const payload: Omit<CreateMappingPayload, "created_by"> = {
      name: `Suggested Mapping (${new Date().toLocaleDateString()} ${new Date().toLocaleTimeString()})`,
      description: `Auto-generated from ${suggestions.length} suggestion clusters with threshold ${suggestionThreshold}`,
      mappings: mappingItems,
      is_active: false,
    };

    await onCreateMapping(payload);
  };

  const SimplePieChart = ({
    data,
    onSelectCluster,
  }: {
    data: { name: string; count: number; isSelected: boolean }[];
    onSelectCluster: (name: string) => void;
  }) => {
    return (
      <div className="flex flex-wrap justify-center gap-4 py-4">
        {data.map((item, index) => (
          <div
            key={index}
            className={`flex cursor-pointer items-center justify-center rounded-full border-2 p-4 transition-all duration-200 ${item.isSelected ? "border-blue-500 shadow-lg" : "border-gray-200"} hover:shadow-md`}
            style={{
              width: `${Math.max(60, Math.min(120, item.count * 15))}px`,
              height: `${Math.max(60, Math.min(120, item.count * 15))}px`,
              opacity:
                item.isSelected || !data.some((d) => d.isSelected) ? 1 : 0.5,
            }}
            onClick={() => onSelectCluster(item.name)}
            title={`${item.name}: ${item.count} fields`}
          >
            <div className="text-center">
              <div className="text-xs font-bold">
                {item.name.substring(0, 8)}
                {item.name.length > 8 ? "..." : ""}
              </div>
              <div className="text-xs">{item.count}</div>
            </div>
          </div>
        ))}
      </div>
    );
  };

  if (error && !isLoading) {
    return (
      <div className="rounded border border-red-500 bg-red-100 p-4 text-red-700">
        <p>Suggestion Tab Error: {error}</p>
      </div>
    );
  }

  return (
    <Card>
      <CardHeader className="space-y-4 p-4">
        <CardDescription>
          Review potential field clusters and suggested canonical names based on
          similarity. Adjust the threshold and generate suggestions.
        </CardDescription>
        <div className="flex flex-wrap items-center gap-4">
          <label
            htmlFor="suggestion-threshold"
            className="text-sm font-medium whitespace-nowrap"
          >
            Similarity Threshold:
          </label>
          <Input
            id="suggestion-threshold"
            type="number"
            min="0"
            max="1"
            step="0.05"
            value={suggestionThreshold}
            onChange={(e) =>
              onSetSuggestionThreshold(parseFloat(e.target.value) || 0)
            }
            className="w-24"
            disabled={isLoading || isSubmitting}
          />
          <Button
            onClick={onGenerateSuggestions}
            disabled={isLoading || isSubmitting}
          >
            {isLoading ? (
              <LoadingSpinner className="mr-2 h-4 w-4 animate-spin" />
            ) : null}{" "}
            Generate Suggestions
          </Button>
          <Button
            onClick={handleCreateMappingFromAllSuggestions}
            disabled={suggestions.length === 0 || isSubmitting || isLoading}
            variant="outline"
          >
            {isSubmitting ? (
              <LoadingSpinner className="mr-2 h-4 w-4 animate-spin" />
            ) : null}{" "}
            Create Mapping from All Suggestions
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-4 p-4">
        {isLoading && suggestions.length === 0 && (
          <div className="flex justify-center p-6">
            <LoadingSpinner /> <p className="ml-2">Generating suggestions...</p>
          </div>
        )}
        {!isLoading && suggestions.length === 0 && (
          <p className="text-muted-foreground p-6 text-center">
            No suggestions generated yet or threshold too high. Adjust and click
            &quot;Generate Suggestions&quot;.
          </p>
        )}
        {!isLoading && suggestions.length > 0 && (
          <div className="mb-6 rounded-lg border p-4">
            <h3 className="mb-3 text-lg font-medium">
              Cluster Distribution (click to select)
            </h3>
            <div className="flex min-h-[150px] items-center justify-center">
              <SimplePieChart
                data={getChartData()}
                onSelectCluster={handleChartClusterSelect}
              />
            </div>
          </div>
        )}
        {suggestions.map((cluster) => (
          <div
            key={cluster.id}
            className={`cursor-pointer rounded-lg border p-1 transition-all duration-200 hover:shadow-md ${selectedClusterId && selectedClusterId !== cluster.id ? "border-transparent opacity-50" : "border-border opacity-100"} ${selectedClusterId === cluster.id ? "ring-primary shadow-lg ring-2" : ""}`}
            onClick={() => onSelectCluster(cluster.id)}
          >
            <SuggestionClusterCard cluster={cluster} />
          </div>
        ))}
      </CardContent>
    </Card>
  );
};

export default SuggestionsTab;
