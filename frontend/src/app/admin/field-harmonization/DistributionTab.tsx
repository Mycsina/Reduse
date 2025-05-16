import React, { useState, useEffect, useCallback, useMemo } from "react";
import DeckGL from "@deck.gl/react";
import { OrbitView, OrbitViewState, LightingEffect } from "@deck.gl/core";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
} from "@/components/ui/layout/table";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import LoadingSpinner from "@/components/ui/loading-spinner";
import {
  FieldDistribution,
  FieldType,
  UmapFieldData,
  FieldEmbeddingsUmapResponse,
} from "@/lib/api/admin/field-harmonization";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { TextLayer } from "@deck.gl/layers";
import { SimpleMeshLayer } from "@deck.gl/mesh-layers";
import { OBJLoader } from "@loaders.gl/obj";
import { AmbientLight, _SunLight as SunLight } from "@deck.gl/core";
import { FieldCluster } from "./page";

interface DistributionTabProps {
  fields: FieldDistribution[]; // From parent
  isLoading: boolean; // Loading state for fields from parent
  error: string | null; // Error for fields from parent

  getColorForType: (
    type: FieldType,
  ) => "default" | "neutral" | "success" | "error" | "warning";
  selectedClusterId: string | null;
  suggestions: FieldCluster[];

  umapData: FieldEmbeddingsUmapResponse | null;
  isUmapLoading: boolean;
  umapError: string | null;
  umapViewState: OrbitViewState; // Current view state from parent
  onUmapViewStateChange: (viewState: OrbitViewState) => void; // To parent
  onRefetchUmap: () => void; // To parent for triggering UMAP refetch
}

const DistributionTab: React.FC<DistributionTabProps> = ({
  fields, // From parent
  isLoading: isLoadingFields,
  error: fieldsError,
  getColorForType,
  selectedClusterId,
  suggestions,
  umapData,
  isUmapLoading,
  umapError,
  umapViewState, // Use this as the source of truth for DeckGL viewState
  onUmapViewStateChange,
  onRefetchUmap,
}) => {
  const [appliedFilter, setAppliedFilter] = useState("all");
  const [showLabels, setShowLabels] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");

  const handleLocalViewStateChange = useCallback(
    (info: { viewState: OrbitViewState }) => {
      onUmapViewStateChange(info.viewState);
      setShowLabels((info.viewState.zoom ?? 0) > 0);
    },
    [onUmapViewStateChange],
  );

  const getFilteredFields = () => {
    let filtered = fields;

    // Apply type filter
    if (appliedFilter !== "all") {
      filtered = filtered.filter((field) => field.field_type === appliedFilter);
    }

    // Apply search filter
    if (searchTerm.trim()) {
      const term = searchTerm.toLowerCase();
      filtered = filtered.filter((field) =>
        field.field_name.toLowerCase().includes(term),
      );
    }

    return filtered;
  };

  const handleFilterChange = (value: string) => {
    setAppliedFilter(value);
  };

  // Helper for mesh color
  const typeColorMapping: Record<FieldType, [number, number, number]> = {
    numeric: [0, 128, 255],
    categorical: [128, 128, 128],
    boolean: [255, 191, 0],
    text: [0, 128, 255],
    mixed: [255, 0, 0],
    unknown: [128, 128, 128],
  };

  const getTypeColorForMesh = useCallback(
    (type: FieldType): [number, number, number] => {
      return typeColorMapping[type] || [128, 128, 128];
    },
    [],
  );

  // Lighting effect for 3D rendering
  const lightingEffect = new LightingEffect({
    ambientLight: new AmbientLight({
      color: [255, 255, 255],
      intensity: 1.0,
    }),
    sunLight: new SunLight({
      timestamp: Date.now(),
      color: [255, 255, 255],
      intensity: 2.0,
    }),
  });

  // Memoize the set of selected field names
  const selectedFieldNames = useMemo(() => {
    if (!selectedClusterId) return new Set<string>();
    const selectedCluster = suggestions.find((c) => c.id === selectedClusterId);
    if (!selectedCluster) return new Set<string>();
    return new Set([
      selectedCluster.canonical_field,
      ...selectedCluster.similar_fields,
    ]);
  }, [selectedClusterId, suggestions]);

  // Generate layers for the 3D visualization
  const getLayers = useCallback(() => {
    if (!umapData || !umapData.fields || umapData.fields.length === 0) {
      return [];
    }
    const sizeScale = 0.1;

    const sphereLayer = new SimpleMeshLayer({
      id: "sphere-layer",
      data: umapData.fields,
      mesh: "/sphere.obj",
      loaders: [OBJLoader],
      getPosition: (d: UmapFieldData) =>
        d.coordinates.length === 3
          ? (d.coordinates as [number, number, number])
          : [d.coordinates[0], d.coordinates[1], 0],
      getColor: (d: UmapFieldData) => {
        const isSelectedField = selectedFieldNames.has(d.name);
        let r = 220,
          g = 220,
          b = 220; // Default: light gray for dots
        let a = 200; // Default alpha

        if (selectedClusterId) {
          // A cluster is selected
          if (isSelectedField) {
            // This dot is part of the selected cluster
            r = 255;
            g = 255;
            b = 255; // Bright white
            a = 255;
          } else {
            // This dot is NOT part of the selected cluster (when another cluster is active)
            r = 70;
            g = 70;
            b = 70; // Dimmer gray
            a = 100; // More transparent
          }
        }
        // If no cluster is selected, default r,g,b,a (220,220,220,200) will be used.
        return [r, g, b, a];
      },
      sizeScale,
      getOrientation: [0, 0, 0],
      material: {
        ambient: 0.6,
        diffuse: 0.6,
        shininess: 32,
        specularColor: [200, 200, 200],
      },
      pickable: true,
      updateTriggers: {
        getColor: [selectedClusterId, selectedFieldNames],
      },
    });

    const labelLayer = new TextLayer({
      id: "text-layer",
      data: umapData.fields,
      getPosition: (d: UmapFieldData) =>
        d.coordinates.length === 3
          ? (d.coordinates as [number, number, number])
          : [d.coordinates[0], d.coordinates[1], 0],
      getText: (d: UmapFieldData) => d.name,
      getSize: 14,
      getColor: (d: UmapFieldData) => {
        // Restoring original TextLayer getColor logic
        const isSelected = selectedFieldNames.has(d.name);
        const alpha = selectedClusterId ? (isSelected ? 255 : 100) : 200;
        return [255, 255, 255, alpha]; // White text
      },
      getAngle: 0,
      getTextAnchor: "middle",
      getAlignmentBaseline: "center",
      getPixelOffset: [0, -10 - sizeScale * 15],
      fontFamily: "sans-serif",
      fontWeight: "bold",
      visible: showLabels,
      pickable: false,
      updateTriggers: {
        getColor: [selectedClusterId, selectedFieldNames],
      },
      parameters: {
        depthCompare: "always",
      },
    });

    return [sphereLayer, labelLayer];
  }, [
    umapData,
    showLabels,
    selectedClusterId,
    selectedFieldNames,
    getTypeColorForMesh,
  ]);

  if (isLoadingFields && fields.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center">
        <LoadingSpinner />
        <p className="ml-2">Loading field distribution...</p>
      </div>
    );
  }

  if (fieldsError) {
    return (
      <div className="rounded border border-red-500 bg-red-100 p-4 text-red-700">
        <p>{fieldsError}</p>
      </div>
    );
  }

  const filteredFields = getFilteredFields();

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
      {/* Field List Column */}
      <div className="lg:col-span-1">
        <Card>
          <CardHeader>
            <CardDescription>Field Details & Distribution</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="mb-4 flex space-x-2">
              <Input
                placeholder="Search field name..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="flex-grow"
              />
              <Select value={appliedFilter} onValueChange={handleFilterChange}>
                <SelectTrigger className="w-[180px]">
                  <SelectValue placeholder="Filter by type" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Types</SelectItem>
                  <SelectItem value="numeric">Numeric</SelectItem>
                  <SelectItem value="categorical">Categorical</SelectItem>
                  <SelectItem value="boolean">Boolean</SelectItem>
                  <SelectItem value="text">Text</SelectItem>
                  <SelectItem value="mixed">Mixed</SelectItem>
                  <SelectItem value="unknown">Unknown</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="max-h-[600px] overflow-y-auto">
              <Table className="min-w-full">
                <TableHeaderCell>Field Name</TableHeaderCell>
                <TableHeaderCell>Type</TableHeaderCell>
                <TableHeaderCell>Count</TableHeaderCell>
                <TableHeaderCell>%</TableHeaderCell>
                <TableBody>
                  {filteredFields.map((field) => (
                    <TableRow key={field.field_name}>
                      <TableCell className="truncate" title={field.field_name}>
                        {field.field_name}
                      </TableCell>
                      <TableCell>
                        <Badge variant={getColorForType(field.field_type)}>
                          {field.field_type}
                        </Badge>
                      </TableCell>
                    </TableRow>
                  ))}
                  {filteredFields.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={4} className="text-center">
                        No fields match your criteria.
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* UMAP Visualization Column */}
      <div className="lg:col-span-2">
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardDescription>
                Field Embeddings UMAP Visualization (3D)
              </CardDescription>
              <Button
                onClick={onRefetchUmap}
                variant="outline"
                size="sm"
                disabled={isUmapLoading}
              >
                {isUmapLoading ? (
                  <LoadingSpinner className="mr-2 h-3 w-3" />
                ) : null}
                Refetch UMAP
              </Button>
            </div>
          </CardHeader>
          <CardContent className="relative h-[600px] bg-black">
            {isUmapLoading && (
              <div className="bg-background/80 absolute inset-0 z-10 flex items-center justify-center">
                <LoadingSpinner />
                <p className="ml-2 text-neutral-200">Loading UMAP data...</p>
              </div>
            )}
            {umapError && (
              <div className="absolute inset-0 flex items-center justify-center bg-red-100 p-4 text-red-700">
                <p>Error loading UMAP: {umapError}</p>
              </div>
            )}
            {!isUmapLoading &&
              !umapError &&
              umapData &&
              umapData.fields.length > 0 && (
                <DeckGL
                  layers={getLayers()}
                  views={
                    new OrbitView({
                      id: "orbit-view",
                      near: 0.01,
                      far: 1000,
                      fovy: 60,
                    })
                  }
                  initialViewState={umapViewState}
                  onViewStateChange={handleLocalViewStateChange}
                  controller={true}
                  effects={[lightingEffect]}
                  parameters={{ blend: true }}
                />
              )}
            {!isUmapLoading &&
              !umapError &&
              (!umapData || umapData.fields.length === 0) && (
                <div className="absolute inset-0 flex items-center justify-center text-gray-400">
                  <p>No UMAP data available or an error occurred.</p>
                </div>
              )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default DistributionTab;
