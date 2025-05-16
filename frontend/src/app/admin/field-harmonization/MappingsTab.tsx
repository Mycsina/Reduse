import React, { useState, useEffect, useCallback } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
} from "@/components/ui/layout/table";
import LoadingSpinner from "@/components/ui/loading-spinner";
import MappingCard from "@/components/admin/MappingCard";
import {
  FieldDistribution,
  FieldHarmonizationMapping,
  FieldMapping,
  CreateMappingPayload,
  UpdateMappingPayload,
} from "@/lib/api/admin/field-harmonization";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import {
  AlertCircle,
  Trash2,
  Edit,
  CheckCircle,
  XCircle,
  PlayCircle,
} from "lucide-react";

interface MappingsTabProps {
  mappings: FieldHarmonizationMapping[];
  activeMappings: FieldHarmonizationMapping[];
  isLoading: boolean;
  error: string | null;
  fields: FieldDistribution[];
  onCreateMapping: (
    payload: Omit<CreateMappingPayload, "created_by">,
  ) => Promise<FieldHarmonizationMapping | null>;
  isCreating: boolean;
  onUpdateMapping: (
    mappingId: string,
    payload: UpdateMappingPayload,
  ) => Promise<FieldHarmonizationMapping | null>;
  isUpdating: boolean;
  onDeleteMapping: (mappingId: string) => Promise<void>;
  isDeleting: boolean;
  onActivateMapping: (
    mappingId: string,
    activate: boolean,
  ) => Promise<FieldHarmonizationMapping | null>;
  isActivating: boolean;
  onApplyRetroactive: (mappingId: string) => Promise<{
    message: string;
    processed_count: number;
    total_updated: number;
  } | null>;
  isApplyingRetroactive: boolean;
}

const initialNewMappingItemState: FieldMapping = {
  original_field: "",
  target_field: "",
};

const initialNewMappingState: Omit<CreateMappingPayload, "created_by"> = {
  name: "",
  description: "",
  mappings: [],
  is_active: false,
};

const mappingsAreEqual = (map1: FieldMapping, map2: FieldMapping): boolean => {
  return (
    map1.original_field === map2.original_field &&
    map1.target_field === map2.target_field
  );
};

const calculateMappingChanges = (
  originalMappings: FieldMapping[],
  newMappings: FieldMapping[],
): {
  mappings_to_add: FieldMapping[];
  mappings_to_remove: FieldMapping[];
} => {
  const originalMap = new Map(
    originalMappings.map((m) => [m.original_field, m]),
  );
  const newMap = new Map(newMappings.map((m) => [m.original_field, m]));

  const mappings_to_add: FieldMapping[] = [];
  const mappings_to_remove: FieldMapping[] = [];

  newMap.forEach((newMapping, key) => {
    if (!originalMap.has(key)) {
      mappings_to_add.push(newMapping);
    } else {
      const originalMapping = originalMap.get(key)!;
      if (!mappingsAreEqual(originalMapping, newMapping)) {
        mappings_to_remove.push(originalMapping);
        mappings_to_add.push(newMapping);
      }
    }
  });

  originalMap.forEach((originalMapping, key) => {
    if (!newMap.has(key)) {
      mappings_to_remove.push(originalMapping);
    }
  });

  return { mappings_to_add, mappings_to_remove };
};

const MappingsTab: React.FC<MappingsTabProps> = ({
  mappings,
  activeMappings,
  isLoading: isLoadingList,
  error: listError,
  fields,
  onCreateMapping,
  isCreating,
  onUpdateMapping,
  isUpdating,
  onDeleteMapping,
  isDeleting,
  onActivateMapping,
  isActivating,
  onApplyRetroactive,
  isApplyingRetroactive,
}) => {
  const [showManageDialog, setShowManageDialog] = useState(false);
  const [mappingToManage, setMappingToManage] = useState<
    Omit<CreateMappingPayload, "created_by" | "is_active"> & {
      is_active?: boolean;
    }
  >(initialNewMappingState);
  const [newMappingItem, setNewMappingItem] = useState<FieldMapping>(
    initialNewMappingItemState,
  );
  const [isEditMode, setIsEditMode] = useState(false);
  const [editMappingId, setEditMappingId] = useState<string | null>(null);
  const [originalEditMappings, setOriginalEditMappings] = useState<
    FieldMapping[]
  >([]);
  const [dialogSubmitError, setDialogSubmitError] = useState<string | null>(
    null,
  );

  const primaryActiveMapping =
    activeMappings.length > 0 ? activeMappings[0] : null;

  const handleOpenCreateDialog = () => {
    setMappingToManage({ ...initialNewMappingState, is_active: false });
    setOriginalEditMappings([]);
    setIsEditMode(false);
    setEditMappingId(null);
    setShowManageDialog(true);
    setDialogSubmitError(null);
  };

  const handleOpenEditDialog = (mapping: FieldHarmonizationMapping) => {
    setMappingToManage({
      name: mapping.name,
      description: mapping.description || "",
      mappings: [...mapping.mappings],
      is_active: mapping.is_active,
    });
    setOriginalEditMappings([...mapping.mappings]);
    setIsEditMode(true);
    setEditMappingId(mapping._id);
    setShowManageDialog(true);
    setDialogSubmitError(null);
  };

  const handleCloseDialog = () => {
    setShowManageDialog(false);
    setNewMappingItem(initialNewMappingItemState);
    setMappingToManage(initialNewMappingState);
    setOriginalEditMappings([]);
    setIsEditMode(false);
    setEditMappingId(null);
    setDialogSubmitError(null);
  };

  const handleAddMappingItem = () => {
    if (
      !newMappingItem.original_field.trim() ||
      !newMappingItem.target_field.trim()
    ) {
      setDialogSubmitError("Original and Target fields cannot be empty.");
      return;
    }
    if (newMappingItem.original_field === newMappingItem.target_field) {
      setDialogSubmitError("Original and Target fields cannot be the same.");
      return;
    }
    if (
      mappingToManage.mappings.some(
        (m) => m.original_field === newMappingItem.original_field,
      )
    ) {
      setDialogSubmitError(
        `Duplicate original field found: ${newMappingItem.original_field}`,
      );
      return;
    }

    setMappingToManage((prev) => ({
      ...prev,
      mappings: [...prev.mappings, { ...newMappingItem }],
    }));
    setNewMappingItem(initialNewMappingItemState);
    setDialogSubmitError(null);
  };

  const handleRemoveMappingItem = (index: number) => {
    setMappingToManage((prev) => ({
      ...prev,
      mappings: prev.mappings.filter((_, i) => i !== index),
    }));
  };

  const handleDialogSubmit = async () => {
    if (!mappingToManage.name.trim()) {
      setDialogSubmitError("Mapping name is required.");
      return;
    }
    if (mappingToManage.mappings.length === 0) {
      setDialogSubmitError("At least one field mapping pair is required.");
      return;
    }
    setDialogSubmitError(null);

    try {
      if (isEditMode && editMappingId) {
        const { mappings_to_add, mappings_to_remove } = calculateMappingChanges(
          originalEditMappings,
          mappingToManage.mappings,
        );
        const payload: UpdateMappingPayload = {
          name:
            mappingToManage.name !==
            mappings.find((m) => m._id === editMappingId)?.name
              ? mappingToManage.name
              : undefined,
          description:
            mappingToManage.description !==
            mappings.find((m) => m._id === editMappingId)?.description
              ? mappingToManage.description
              : undefined,
          mappings_to_add:
            mappings_to_add.length > 0 ? mappings_to_add : undefined,
          mappings_to_remove:
            mappings_to_remove.map((m) => m.original_field).length > 0
              ? mappings_to_remove.map((m) => m.original_field)
              : undefined,
        };
        if (
          !payload.mappings_to_add &&
          !payload.mappings_to_remove &&
          mappingToManage.name ===
            mappings.find((m) => m._id === editMappingId)?.name &&
          mappingToManage.description ===
            mappings.find((m) => m._id === editMappingId)?.description
        ) {
          const originalMapping = mappings.find((m) => m._id === editMappingId);
          if (
            originalMapping &&
            mappingToManage.is_active !== undefined &&
            originalMapping.is_active !== mappingToManage.is_active
          ) {
            await onActivateMapping(editMappingId, !!mappingToManage.is_active);
          }
          handleCloseDialog();
          return;
        }
        await onUpdateMapping(editMappingId, payload);
      } else {
        const payload: Omit<CreateMappingPayload, "created_by"> = {
          name: mappingToManage.name,
          description: mappingToManage.description,
          mappings: mappingToManage.mappings,
          is_active: !!mappingToManage.is_active,
        };
        await onCreateMapping(payload);
      }
      handleCloseDialog();
    } catch (err) {
      console.error("Dialog submit error:", err);
      setDialogSubmitError((err as Error).message || "Failed to save mapping.");
    }
  };

  const handleDelete = async (mappingId: string) => {
    try {
      await onDeleteMapping(mappingId);
    } catch (e) {
      console.error(e);
    }
  };

  const handleToggleActive = async (mapping: FieldHarmonizationMapping) => {
    try {
      await onActivateMapping(mapping._id, !mapping.is_active);
    } catch (e) {
      console.error(e);
    }
  };

  const handleRetroactive = async () => {
    if (primaryActiveMapping) {
      try {
        await onApplyRetroactive(primaryActiveMapping._id);
      } catch (e) {
        console.error(e);
      }
    }
  };

  const availableOriginalFields = fields.map((f) => f.field_name).sort();
  const allTargetFields = new Set<string>();
  mappings.forEach((mOuter) =>
    mOuter.mappings.forEach((mInner) =>
      allTargetFields.add(mInner.target_field),
    ),
  );
  fields.forEach((f) => allTargetFields.add(f.field_name));
  const availableTargetFields = Array.from(allTargetFields).sort();

  if (isLoadingList)
    return (
      <div className="flex justify-center p-6">
        <LoadingSpinner />
        <p className="ml-2">Loading mappings...</p>
      </div>
    );
  if (listError)
    return (
      <div className="p-4 text-red-500">
        Error loading mappings: {listError}
      </div>
    );

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardDescription>
              Manage field harmonization mappings. The primary active mapping is
              used for new listings.
            </CardDescription>
            {primaryActiveMapping && (
              <p className="text-muted-foreground text-sm">
                Active mapping: <strong>{primaryActiveMapping.name}</strong>{" "}
                (ID: {primaryActiveMapping._id})
              </p>
            )}
            {!primaryActiveMapping && (
              <p className="text-sm text-orange-500">
                No mapping is currently active.
              </p>
            )}
          </div>
          <Button
            onClick={handleOpenCreateDialog}
            disabled={isCreating || isUpdating}
          >
            Create New Mapping
          </Button>
        </CardHeader>
        <CardContent>
          {mappings.length === 0 && (
            <p className="text-muted-foreground py-4 text-center">
              No mappings created yet.
            </p>
          )}
          <div className="space-y-4">
            {mappings.map((mapping) => (
              <MappingCard
                key={mapping._id}
                mapping={mapping}
                onEdit={() => handleOpenEditDialog(mapping)}
                onDelete={() => handleDelete(mapping._id)}
                onApply={(mappingId) => {
                  const mappingToToggle = mappings.find(
                    (m) => m._id === mappingId,
                  );
                  if (mappingToToggle) {
                    handleToggleActive(mappingToToggle);
                  }
                }}
                onUpdate={() => {}}
                isSubmitting={isDeleting || isActivating || isUpdating}
              />
            ))}
          </div>
        </CardContent>
      </Card>

      {primaryActiveMapping && (
        <Card>
          <CardHeader>
            <CardDescription>
              Apply active mapping retroactively to all existing listings.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button
              onClick={handleRetroactive}
              disabled={isApplyingRetroactive || !primaryActiveMapping}
              variant="outline"
            >
              {isApplyingRetroactive && (
                <LoadingSpinner className="mr-2 h-4 w-4 animate-spin" />
              )}
              Apply Active Mapping Retroactively
            </Button>
            {isApplyingRetroactive && (
              <p className="text-muted-foreground mt-2 text-sm">
                This may take some time...
              </p>
            )}
          </CardContent>
        </Card>
      )}

      <Dialog open={showManageDialog} onOpenChange={setShowManageDialog}>
        <DialogContent className="sm:max-w-[600px]">
          <DialogHeader>
            <DialogTitle>
              {isEditMode ? "Edit" : "Create New"} Field Mapping
            </DialogTitle>
            <DialogDescription>
              {isEditMode
                ? "Modify the details of this mapping."
                : "Define original field names and their target canonical names."}
            </DialogDescription>
          </DialogHeader>
          <div className="grid max-h-[60vh] gap-4 overflow-y-auto py-4 pr-2">
            <div className="space-y-1">
              <Label htmlFor="mapping-name">Name</Label>
              <Input
                id="mapping-name"
                value={mappingToManage.name}
                onChange={(e) =>
                  setMappingToManage((prev) => ({
                    ...prev,
                    name: e.target.value,
                  }))
                }
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="mapping-desc">Description (Optional)</Label>
              <Input
                id="mapping-desc"
                value={mappingToManage.description}
                onChange={(e) =>
                  setMappingToManage((prev) => ({
                    ...prev,
                    description: e.target.value,
                  }))
                }
              />
            </div>
            {isEditMode && editMappingId && (
              <div className="flex items-center space-x-2 py-2">
                <Switch
                  id={`is_active-switch-${editMappingId}`}
                  checked={mappingToManage.is_active}
                  onCheckedChange={(checked) =>
                    setMappingToManage((prev) => ({
                      ...prev,
                      is_active: checked,
                    }))
                  }
                />
                <Label htmlFor={`is_active-switch-${editMappingId}`}>
                  Set as active mapping
                </Label>
              </div>
            )}
            {!isEditMode && (
              <div className="flex items-center space-x-2 py-2">
                <Switch
                  id={`is_active-switch-new`}
                  checked={mappingToManage.is_active}
                  onCheckedChange={(checked) =>
                    setMappingToManage((prev) => ({
                      ...prev,
                      is_active: checked,
                    }))
                  }
                />
                <Label htmlFor={`is_active-switch-new`}>
                  Set as active mapping upon creation
                </Label>
              </div>
            )}

            <h4 className="pt-2 font-semibold">Mapping Pairs:</h4>
            <div className="space-y-2 rounded-md border p-3">
              <div className="flex items-end gap-2">
                <div className="flex-1 space-y-1">
                  <Label htmlFor="original-field">Original Field</Label>
                  <Select
                    value={newMappingItem.original_field}
                    onValueChange={(value) =>
                      setNewMappingItem((prev) => ({
                        ...prev,
                        original_field: value,
                      }))
                    }
                  >
                    <SelectTrigger id="original-field">
                      <SelectValue placeholder="Select original field" />
                    </SelectTrigger>
                    <SelectContent>
                      {availableOriginalFields.map((f) => (
                        <SelectItem key={f} value={f}>
                          {f}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="flex-1 space-y-1">
                  <Label htmlFor="target-field">Target Field</Label>
                  <Input
                    list="target-field-suggestions"
                    id="target-field"
                    value={newMappingItem.target_field}
                    onChange={(e) =>
                      setNewMappingItem((prev) => ({
                        ...prev,
                        target_field: e.target.value,
                      }))
                    }
                    placeholder="Enter target field name"
                  />
                  <datalist id="target-field-suggestions">
                    {availableTargetFields.map((f) => (
                      <option key={f} value={f} />
                    ))}
                  </datalist>
                </div>
                <Button
                  onClick={handleAddMappingItem}
                  variant="outline"
                  size="sm"
                  className="shrink-0"
                >
                  Add Pair
                </Button>
              </div>
              {mappingToManage.mappings.length > 0 && (
                <div className="mt-3 max-h-[200px] overflow-y-auto">
                  <Table>
                    <TableHeaderCell>Original</TableHeaderCell>
                    <TableHeaderCell>Target</TableHeaderCell>
                    <TableHeaderCell>Actions</TableHeaderCell>
                    <TableBody>
                      {mappingToManage.mappings.map((item, index) => (
                        <TableRow key={index}>
                          <TableCell>{item.original_field}</TableCell>
                          <TableCell>{item.target_field}</TableCell>
                          <TableCell>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleRemoveMappingItem(index)}
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}
            </div>
            {dialogSubmitError && (
              <p className="flex items-center text-sm text-red-500">
                <AlertCircle className="mr-1 h-4 w-4" /> {dialogSubmitError}
              </p>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={handleCloseDialog}>
              Cancel
            </Button>
            <Button
              onClick={handleDialogSubmit}
              disabled={isCreating || isUpdating}
            >
              {(isCreating || isUpdating) && (
                <LoadingSpinner className="mr-2 h-4 w-4 animate-spin" />
              )}
              {isEditMode ? "Save Changes" : "Create Mapping"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default MappingsTab;
