"use client";

import { useState, useMemo, useCallback, useEffect, useRef, memo } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { FilterCondition, FilterGroup } from "@/lib/api/query/query";
import { useSearchParams, useRouter } from "next/navigation";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Command,
  CommandInput,
  CommandList,
  CommandEmpty,
  CommandItem,
} from "@/components/ui/command";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Check, ChevronsUpDown, Plus, Trash2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { debounce } from "lodash";
import { useVirtualizer, type Virtualizer } from "@tanstack/react-virtual";
import { useAvailableFields } from "@/lib/api/query/query";

interface AdvancedFilterProps {
  initialFilterGroup?: FilterGroup | null;
  onFilterChange: (filter: FilterGroup | null) => void;
}

const VirtualizedItems = memo(function VirtualizedItems({
  items,
  value,
  onSelect,
}: {
  items: string[];
  value: string;
  onSelect: (value: string) => void;
}) {
  const parentRef = useRef<HTMLDivElement>(null);

  const rowVirtualizer: Virtualizer<HTMLDivElement, Element> = useVirtualizer({
    count: items.length,
    getScrollElement: () => parentRef.current,
    estimateSize: useCallback(() => 36, []),
    overscan: 5,
  });

  return (
    <div ref={parentRef} className="max-h-[300px] overflow-auto">
      <div
        style={{
          height: `${rowVirtualizer.getTotalSize()}px`,
          width: "100%",
          position: "relative",
        }}
      >
        {rowVirtualizer.getVirtualItems().map((virtualRow) => {
          const item = items[virtualRow.index];
          return (
            <CommandItem
              key={virtualRow.index}
              value={item}
              onSelect={onSelect}
              className="absolute top-0 left-0 w-full"
              style={{
                height: `${virtualRow.size}px`,
                transform: `translateY(${virtualRow.start}px)`,
              }}
            >
              <Check
                className={cn(
                  "mr-2 h-4 w-4",
                  value === item ? "opacity-100" : "opacity-0",
                )}
              />
              {item}
            </CommandItem>
          );
        })}
      </div>
    </div>
  );
});

function VirtualizedCommandList({
  items,
  value,
  onSelect,
}: {
  items: string[];
  value: string;
  onSelect: (value: string) => void;
}) {
  return (
    <CommandList>
      {items.length === 0 ? (
        <CommandEmpty>No fields found.</CommandEmpty>
      ) : (
        <VirtualizedItems items={items} value={value} onSelect={onSelect} />
      )}
    </CommandList>
  );
}

function getMatchScore(str: string, search: string): number {
  const strLower = str.toLowerCase();
  const searchLower = search.toLowerCase();

  // Exact match gets highest score
  if (strLower === searchLower) return 1000;
  // Starts with gets high score
  if (strLower.startsWith(searchLower)) return 100;
  // Contains gets medium score, weighted by position
  const index = strLower.indexOf(searchLower);
  if (index >= 0) return 50 - index * 0.1;

  // No match gets lowest score
  return 0;
}

function ConditionComponent({
  initialCondition,
  onUpdate,
  onDelete,
  level = 0,
}: {
  initialCondition: FilterCondition;
  onUpdate: (updated: FilterCondition) => void;
  onDelete: () => void;
  level?: number;
}) {
  const [open, setOpen] = useState(false);
  const [fieldValue, setFieldValue] = useState(initialCondition.field);
  const [operatorValue, setOperatorValue] = useState(
    initialCondition.operator || "CONTAINS",
  );
  const [textValue, setTextValue] = useState(initialCondition.value);
  const [search, setSearch] = useState("");

  // Use React Query with better caching
  const { data: fields, isLoading } = useAvailableFields();

  // Update local state when condition changes
  useEffect(() => {
    setFieldValue(initialCondition.field);
    setOperatorValue(initialCondition.operator || "CONTAINS");
    setTextValue(initialCondition.value);
  }, [
    initialCondition.field,
    initialCondition.operator,
    initialCondition.value,
  ]);

  // Memoize the available fields with useMemo
  const availableFields = useMemo(() => {
    if (!fields) return [];
    return Array.from(
      new Set([...fields.main_fields, ...fields.info_fields]),
    ).sort();
  }, [fields]);

  // Memoize filtered fields with debounced search and relevance sorting
  const filteredFields = useMemo(() => {
    if (!search.trim()) return availableFields;
    const searchLower = search.toLowerCase();

    return [...availableFields]
      .map((field) => ({
        field,
        score: getMatchScore(field, searchLower),
      }))
      .filter((item) => item.score > 0)
      .sort((a, b) => b.score - a.score)
      .map((item) => item.field);
  }, [availableFields, search]);

  // Debounce search updates
  const debouncedSetSearch = useCallback(
    debounce((value: string) => {
      setSearch(value.toLowerCase());
    }, 150),
    [],
  );

  const handleSelectField = useCallback(
    (currentValue: string) => {
      // Defer state update to avoid flushSync during render
      queueMicrotask(() => {
        setFieldValue(currentValue);
        onUpdate({
          field: currentValue,
          operator: operatorValue as FilterCondition["operator"], // Ensure type safety
          value: textValue,
        });
      });
      // Close the popover immediately
      setOpen(false);
    },
    [onUpdate, operatorValue, textValue], // setOpen is stable, no need to add
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter") {
        e.preventDefault();
        if (search && filteredFields.length > 0) {
          const firstMatch = filteredFields[0];
          handleSelectField(firstMatch);
        }
      }
    },
    [search, filteredFields, handleSelectField],
  );

  const handleOperatorChange = useCallback(
    (newOperator: string) => {
      setOperatorValue(newOperator as FilterCondition["operator"]);
      onUpdate({
        field: fieldValue,
        operator: newOperator as FilterCondition["operator"],
        value: textValue,
      });
    },
    [fieldValue, onUpdate, textValue],
  );

  const handleValueChange = useCallback(
    (newValue: string) => {
      setTextValue(newValue);
      onUpdate({
        field: fieldValue,
        operator: operatorValue as FilterCondition["operator"],
        value: newValue,
      });
    },
    [fieldValue, onUpdate, operatorValue],
  );

  return (
    <div
      className="mb-2 flex items-center gap-2"
      style={{ marginLeft: `${level * 20}px` }}
    >
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button
            variant="outline"
            role="combobox"
            aria-expanded={open}
            className="min-w-[200px] justify-between"
            disabled={isLoading}
          >
            {isLoading
              ? "Loading fields..."
              : fieldValue
                ? fieldValue
                : "Select field..."}
            <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
          </Button>
        </PopoverTrigger>
        <PopoverContent
          className="w-[200px] p-0"
          onOpenAutoFocus={(e) => e.preventDefault()}
          sideOffset={4}
        >
          <Command shouldFilter={false} className="w-full">
            <CommandInput
              placeholder="Search fields..."
              onValueChange={debouncedSetSearch}
              onKeyDown={handleKeyDown}
            />
            <VirtualizedCommandList
              items={filteredFields}
              value={fieldValue}
              onSelect={handleSelectField}
            />
          </Command>
        </PopoverContent>
      </Popover>
      <Select value={operatorValue} onValueChange={handleOperatorChange}>
        <SelectTrigger className="w-[120px]">
          <SelectValue placeholder="Operator" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="CONTAINS">Contains</SelectItem>
          <SelectItem value="EQUALS">Equals (Text)</SelectItem>
          <SelectItem value="REGEX">Regex</SelectItem>
          <SelectItem value="EQ_NUM">Equals (Num)</SelectItem>
          <SelectItem value="GT">{`>`}</SelectItem>
          <SelectItem value="LT">{`<`}</SelectItem>
          <SelectItem value="GTE">{`>=`}</SelectItem>
          <SelectItem value="LTE">{`<=`}</SelectItem>
        </SelectContent>
      </Select>
      <Input
        placeholder="Value..."
        value={textValue}
        onChange={(e) => handleValueChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            // The parent component will handle the filter update
          }
        }}
        className="flex-1"
      />
      <Button variant="ghost" size="icon" onClick={onDelete}>
        <Trash2 className="h-4 w-4" />
      </Button>
    </div>
  );
}

function GroupComponent({
  group,
  onUpdate,
  onDelete,
  level = 0,
}: {
  group: FilterGroup;
  onUpdate: (updated: FilterGroup) => void;
  onDelete: () => void;
  level?: number;
}) {
  const addCondition = () => {
    onUpdate({
      ...group,
      conditions: [
        ...group.conditions,
        { field: "", operator: "CONTAINS", value: "" },
      ],
    });
  };

  const addGroup = () => {
    onUpdate({
      ...group,
      conditions: [...group.conditions, { type: "AND", conditions: [] }],
    });
  };

  const updateCondition = (
    index: number,
    updated: FilterCondition | FilterGroup,
  ) => {
    const newConditions = [...group.conditions];
    newConditions[index] = updated;
    onUpdate({ ...group, conditions: newConditions });
  };

  const deleteCondition = (index: number) => {
    onUpdate({
      ...group,
      conditions: group.conditions.filter((_, i) => i !== index),
    });
  };

  return (
    <div className="space-y-2" style={{ marginLeft: `${level * 20}px` }}>
      <div className="flex items-center gap-2">
        <Select
          value={group.type}
          onValueChange={(value: "AND" | "OR") =>
            onUpdate({ ...group, type: value })
          }
        >
          <SelectTrigger className="w-[100px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="AND">AND</SelectItem>
            <SelectItem value="OR">OR</SelectItem>
          </SelectContent>
        </Select>
        <Button variant="outline" size="sm" onClick={addCondition}>
          <Plus className="mr-2 h-4 w-4" />
          Add Condition
        </Button>
        <Button variant="outline" size="sm" onClick={addGroup}>
          <Plus className="mr-2 h-4 w-4" />
          Add Group
        </Button>
        {level > 0 && (
          <Button variant="ghost" size="icon" onClick={onDelete}>
            <Trash2 className="h-4 w-4" />
          </Button>
        )}
      </div>
      <div className="space-y-2">
        {group.conditions.map((condition, index) => (
          <div key={index}>
            {"type" in condition ? (
              <GroupComponent
                group={condition as FilterGroup}
                onUpdate={(updated) => updateCondition(index, updated)}
                onDelete={() => deleteCondition(index)}
                level={level + 1}
              />
            ) : (
              <ConditionComponent
                initialCondition={condition as FilterCondition}
                onUpdate={(updated) => updateCondition(index, updated)}
                onDelete={() => deleteCondition(index)}
                level={level + 1}
              />
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

export default function AdvancedFilter({
  initialFilterGroup,
  onFilterChange,
}: AdvancedFilterProps) {
  const searchParams = useSearchParams();
  const router = useRouter();
  const [rootGroup, setRootGroup] = useState<FilterGroup>(
    initialFilterGroup || { type: "AND", conditions: [] },
  );

  useEffect(() => {
    setRootGroup(initialFilterGroup || { type: "AND", conditions: [] });
  }, [initialFilterGroup]);

  const handleRootUpdate = useCallback((updated: FilterGroup) => {
    if (
      updated &&
      typeof updated === "object" &&
      "type" in updated &&
      "conditions" in updated
    ) {
      setRootGroup(updated);
    }
  }, []);

  useEffect(() => {
    if (rootGroup.conditions.length > 0) {
      onFilterChange(rootGroup);
    } else {
      onFilterChange(null);
    }
  }, [rootGroup, onFilterChange]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter") {
        e.preventDefault();
        onFilterChange(rootGroup.conditions.length > 0 ? rootGroup : null);
      }
    },
    [rootGroup, onFilterChange],
  );

  return (
    <div
      className="mb-4 space-y-4 rounded-lg border p-4"
      onKeyDown={handleKeyDown}
    >
      <GroupComponent
        group={rootGroup}
        onUpdate={handleRootUpdate}
        onDelete={() => setRootGroup({ type: "AND", conditions: [] })}
        level={0}
      />
    </div>
  );
}
