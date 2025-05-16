"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { CronSelector } from "@/components/ui/cronSelector";
import {
  Command,
  CommandInput,
  CommandList,
  CommandEmpty,
  CommandGroup,
  CommandItem,
} from "@/components/ui/command";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Check, ChevronsUpDown } from "lucide-react";
import { cn } from "@/lib/utils";

import {
  useAvailableFunctions,
  useFunctionInfo,
  useScheduleFunctionMutation,
  type FunctionInfo,
} from "@/lib/api/admin/tasks";

interface FunctionParameterUI {
  required: boolean;
  default: any;
  type: string;
  description: string | null;
}

interface FunctionUI {
  path: string;
  name: string;
  module: string;
  doc: string | null; // doc can be null
  is_async: boolean;
  parameters: Record<string, FunctionParameterUI>;
  return_type: string | null; // return_type can be null
  full_path: string;
}

// Define ApiParameterInfo based on FunctionInfo.parameters structure
type ApiParameterInfo = FunctionInfo["parameters"][string];

const parseValue = (value: any, type: string): any => {
  if (value === null || value === undefined || value === "") {
    if (type.toLowerCase() === "bool" || type.toLowerCase() === "boolean")
      return false;
    return null;
  }
  try {
    switch (type.toLowerCase()) {
      case "str":
      case "string":
        return String(value);
      case "int":
      case "integer":
        return parseInt(value, 10);
      case "float":
      case "number":
        return parseFloat(value);
      case "bool":
      case "boolean":
        if (typeof value === "string") return value.toLowerCase() === "true";
        return Boolean(value);
      // Basic list/dict parsing, assuming simple comma-separated for list string & JSON for dict string
      case "list":
      case "array":
        if (typeof value === "string")
          return value
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean);
        return Array.isArray(value) ? value : [value];
      case "dict":
      case "object":
        if (typeof value === "string") {
          try {
            return JSON.parse(value);
          } catch {
            return {};
          }
        }
        return value;
      default: // For more complex like List[int] or Dict[str, int], this is simplified
        return value;
    }
  } catch (error) {
    console.error(`Error parsing value ${value} as type ${type}:`, error);
    return null;
  }
};

export default function FunctionScheduler() {
  const [selectedFunctionPath, setSelectedFunctionPath] = useState<string>("");
  const [openPopover, setOpenPopover] = useState(false);
  const [search, setSearch] = useState("");
  const [config, setConfig] = useState({
    cron: "0 0 * * *",
    enabled: true,
    max_instances: 1,
    parameters: {} as Record<string, any>,
  });

  const {
    data: availableFunctionsData,
    isLoading: isLoadingFunctions,
    isError: isErrorFunctions,
    error: functionsError,
  } = useAvailableFunctions();

  const functionsForUI: FunctionUI[] =
    availableFunctionsData?.map((func: FunctionInfo) => ({
      ...func,
      path: func.full_path,
      name: func.function_name,
      module: func.module_name,
      doc: func.doc ?? null, // Ensure doc is null if undefined
      return_type: func.return_type ?? null, // Ensure return_type is null if undefined
      parameters: Object.entries(func.parameters).reduce(
        (acc, [key, value]) => {
          const paramInfo = value as ApiParameterInfo;
          acc[key] = {
            required: paramInfo.required || false,
            default: paramInfo.default,
            type: paramInfo.type || "string",
            description: paramInfo.description,
          };
          return acc;
        },
        {} as Record<string, FunctionParameterUI>,
      ),
    })) || [];

  const {
    data: selectedFunctionInfoData,
    isLoading: isLoadingFunctionInfo,
    isError: isErrorFunctionInfo,
    error: functionInfoError,
  } = useFunctionInfo(selectedFunctionPath);

  const functionInfoForUI: FunctionUI | null = selectedFunctionInfoData
    ? {
        ...(selectedFunctionInfoData as FunctionInfo),
        path: selectedFunctionInfoData.full_path,
        name: selectedFunctionInfoData.function_name,
        module: selectedFunctionInfoData.module_name,
        doc: selectedFunctionInfoData.doc ?? null,
        return_type: selectedFunctionInfoData.return_type ?? null,
        parameters: Object.entries(selectedFunctionInfoData.parameters).reduce(
          (acc, [key, value]) => {
            const paramInfo = value as ApiParameterInfo;
            acc[key] = {
              required: paramInfo.required || false,
              default: paramInfo.default,
              type: paramInfo.type || "string",
              description: paramInfo.description,
            };
            return acc;
          },
          {} as Record<string, FunctionParameterUI>,
        ),
      }
    : null;

  const scheduleFunctionMutation = useScheduleFunctionMutation();

  useEffect(() => {
    if (functionInfoForUI) {
      const defaultParams = Object.entries(functionInfoForUI.parameters).reduce(
        (acc, [key, info]) => ({
          ...acc,
          [key]:
            info.default !== undefined
              ? info.default
              : info.type === "bool" || info.type === "boolean"
                ? false
                : "",
        }),
        {},
      );
      setConfig((prev) => ({ ...prev, parameters: defaultParams }));
    } else {
      setConfig((prev) => ({ ...prev, parameters: {} }));
    }
  }, [functionInfoForUI]);

  const updateConfigField = (
    field: keyof typeof config | `parameters.${string}`,
    value: any,
  ) => {
    setConfig((prev) => {
      if (typeof field === "string" && field.startsWith("parameters.")) {
        const paramName = field.substring("parameters.".length);
        return {
          ...prev,
          parameters: { ...prev.parameters, [paramName]: value },
        };
      }
      return { ...prev, [field]: value };
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFunctionPath || !functionInfoForUI) {
      console.error("Please select a function");
      return;
    }

    const parsedParams = Object.entries(config.parameters).reduce(
      (acc, [key, value]) => {
        const paramInfo = functionInfoForUI.parameters[key];
        if (paramInfo) {
          const parsed = parseValue(value, paramInfo.type);
          if (parsed !== null || !paramInfo.required || value === "") {
            // Allow empty strings for optional non-null types
            acc[key] = parsed;
          } else if (paramInfo.required && parsed === null && value !== "") {
            acc[key] = null;
          }
        }
        return acc;
      },
      {} as Record<string, any>,
    );

    try {
      await scheduleFunctionMutation.mutateAsync({
        functionPath: functionInfoForUI.full_path,
        config: {
          cron: config.cron,
          enabled: config.enabled,
          max_instances: config.max_instances,
          parameters: parsedParams,
        },
      });
      setSelectedFunctionPath("");
      setConfig({
        cron: "0 0 * * *",
        enabled: true,
        max_instances: 1,
        parameters: {},
      });
    } catch (error) {
      console.error("Failed to schedule function:", error);
    }
  };

  const renderParameterField = (name: string, info: FunctionParameterUI) => {
    const value = config.parameters[name];
    const label = `${name}${info.required ? " *" : ""}`;
    const paramId = `func-sched-param-${name}`;

    if (
      info.type.toLowerCase() === "bool" ||
      info.type.toLowerCase() === "boolean"
    ) {
      return (
        <div
          key={name}
          className="flex items-center justify-between space-x-2 py-2"
        >
          <Label htmlFor={paramId} className="flex flex-col">
            <span>{label}</span>
            {info.description && (
              <span className="text-xs font-normal text-gray-400">
                {info.description}
              </span>
            )}
          </Label>
          <Switch
            id={paramId}
            checked={!!value}
            onCheckedChange={(checked) =>
              updateConfigField(`parameters.${name}`, checked)
            }
          />
        </div>
      );
    }
    if (
      info.type.toLowerCase() === "int" ||
      info.type.toLowerCase() === "integer" ||
      info.type.toLowerCase() === "number" ||
      info.type.toLowerCase() === "float"
    ) {
      return (
        <div key={name} className="space-y-1 py-1">
          <Label htmlFor={paramId}>
            {label}
            {info.description && (
              <span className="ml-1 text-xs font-normal text-gray-400">
                ({info.description})
              </span>
            )}
          </Label>
          <Input
            id={paramId}
            type="number"
            value={value ?? ""}
            onChange={(e) =>
              updateConfigField(`parameters.${name}`, e.target.value)
            }
            required={info.required}
            step={info.type.toLowerCase().includes("float") ? "any" : "1"}
          />
        </div>
      );
    }
    if (
      info.type.toLowerCase() === "list" ||
      info.type.toLowerCase() === "array"
    ) {
      return (
        <div key={name} className="space-y-1 py-1">
          <Label htmlFor={paramId}>
            {label}
            {info.description && (
              <span className="ml-1 text-xs font-normal text-gray-400">
                ({info.description})
              </span>
            )}
          </Label>
          <Input
            id={paramId}
            value={Array.isArray(value) ? value.join(", ") : (value ?? "")}
            onChange={(e) =>
              updateConfigField(`parameters.${name}`, e.target.value)
            }
            placeholder="Comma-separated values"
            required={info.required}
          />
        </div>
      );
    }
    return (
      <div key={name} className="space-y-1 py-1">
        <Label htmlFor={paramId}>
          {label}
          {info.description && (
            <span className="ml-1 text-xs font-normal text-gray-400">
              ({info.description})
            </span>
          )}
        </Label>
        <Input
          id={paramId}
          value={value ?? ""}
          onChange={(e) =>
            updateConfigField(`parameters.${name}`, e.target.value)
          }
          required={info.required}
        />
      </div>
    );
  };

  if (isLoadingFunctions) return <p>Loading available functions...</p>;
  if (isErrorFunctions)
    return <p>Error loading functions: {functionsError?.message}</p>;

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {/* Function Selector Popover */}
      <div className="space-y-2">
        <Label>Function to Schedule</Label>
        <Popover open={openPopover} onOpenChange={setOpenPopover}>
          <PopoverTrigger asChild>
            <Button
              variant="outline"
              role="combobox"
              aria-expanded={openPopover}
              className="w-full justify-between truncate"
              disabled={
                isLoadingFunctionInfo || scheduleFunctionMutation.isPending
              }
            >
              {selectedFunctionPath
                ? functionsForUI.find(
                    (f) => f.full_path === selectedFunctionPath,
                  )?.name || "Select function..."
                : "Select function..."}
              <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
            </Button>
          </PopoverTrigger>
          <PopoverContent className="max-h-[--radix-popover-content-available-height] w-[--radix-popover-trigger-width] p-0">
            <Command>
              <CommandInput
                placeholder="Search function..."
                value={search}
                onValueChange={setSearch}
              />
              <CommandList>
                <CommandEmpty>No function found.</CommandEmpty>
                <CommandGroup>
                  {functionsForUI
                    .filter(
                      (func) =>
                        func.name
                          .toLowerCase()
                          .includes(search.toLowerCase()) ||
                        func.module
                          .toLowerCase()
                          .includes(search.toLowerCase()),
                    )
                    .map((func) => (
                      <CommandItem
                        key={func.full_path}
                        value={func.full_path}
                        onSelect={(currentValue) => {
                          setSelectedFunctionPath(
                            currentValue === selectedFunctionPath
                              ? ""
                              : currentValue,
                          );
                          setOpenPopover(false);
                          setSearch("");
                        }}
                      >
                        <Check
                          className={cn(
                            "mr-2 h-4 w-4",
                            selectedFunctionPath === func.full_path
                              ? "opacity-100"
                              : "opacity-0",
                          )}
                        />
                        <div className="flex flex-col">
                          <span>{func.name}</span>
                          <span className="text-xs text-gray-400">
                            {func.module}
                          </span>
                        </div>
                      </CommandItem>
                    ))}
                </CommandGroup>
              </CommandList>
            </Command>
          </PopoverContent>
        </Popover>
      </div>

      {isLoadingFunctionInfo && <p>Loading function details...</p>}
      {isErrorFunctionInfo && <p>Error: {functionInfoError?.message}</p>}

      {functionInfoForUI && (
        <div className="mt-4 space-y-4 border-t pt-4">
          <Label className="text-lg font-semibold">
            Parameters for {functionInfoForUI.name}
          </Label>
          {functionInfoForUI.doc && (
            <p className="mb-3 text-sm text-gray-500 italic">
              {functionInfoForUI.doc}
            </p>
          )}
          {Object.keys(functionInfoForUI.parameters).length === 0 && (
            <p className="text-sm text-gray-500">
              This function takes no parameters.
            </p>
          )}
          {Object.entries(functionInfoForUI.parameters).map(([name, info]) =>
            renderParameterField(name, info),
          )}
        </div>
      )}

      {/* Common Scheduling Fields (CRON, Enabled, Max Instances) */}
      {selectedFunctionPath && functionInfoForUI && (
        <div className="mt-6 space-y-6 border-t pt-6">
          <Label className="text-lg font-semibold">Scheduling Options</Label>
          <div className="space-y-2">
            <Label htmlFor="cron-scheduler">CRON String</Label>
            <CronSelector
              value={config.cron}
              onChange={(cron) => updateConfigField("cron", cron)}
            />
          </div>
          <div className="flex items-center justify-between">
            <Label htmlFor="enabled-scheduler-switch" className="flex flex-col">
              <span>Enable Schedule</span>
              <span className="text-xs font-normal text-gray-500">
                Toggle to enable or disable this job.
              </span>
            </Label>
            <Switch
              id="enabled-scheduler-switch"
              checked={config.enabled}
              onCheckedChange={(checked) =>
                updateConfigField("enabled", checked)
              }
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="max_instances-scheduler">Max Instances</Label>
            <Input
              id="max_instances-scheduler"
              type="number"
              value={config.max_instances}
              onChange={(e) =>
                updateConfigField(
                  "max_instances",
                  parseInt(e.target.value, 10) || 1,
                )
              }
              min={1}
            />
          </div>
        </div>
      )}

      <Button
        type="submit"
        className="mt-6 w-full"
        disabled={
          !selectedFunctionPath ||
          isLoadingFunctionInfo ||
          scheduleFunctionMutation.isPending
        }
      >
        {scheduleFunctionMutation.isPending
          ? "Scheduling..."
          : "Schedule Function"}
      </Button>
    </form>
  );
}
