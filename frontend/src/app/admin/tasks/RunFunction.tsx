"use client";

import { useState, useEffect, useRef } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "@/hooks/use-toast";
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
import { Card } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import apiClient from "@/lib/api-client"; // Keep for subscribeToJobLogs
import { Title } from "@/components/ui/text/Title"; // Corrected import for Title

// Import React Query hooks and types
import {
  useAvailableFunctions,
  useFunctionInfo,
  useRunFunctionMutation,
  subscribeToJobLogs,
  type FunctionInfo,
} from "@/lib/api/admin/tasks";

interface FunctionParameterUI {
  required: boolean;
  default: any;
  type: string;
  description: string | null;
}

interface FunctionUI {
  path: string; // Typically full_path from API
  name: string; // function_name from API
  module: string; // module_name from API
  doc: string | null;
  is_async: boolean;
  parameters: Record<string, FunctionParameterUI>;
  return_type: string | null;
  full_path: string;
}

// Define ApiParameterInfo based on FunctionInfo.parameters structure
type ApiParameterInfo = FunctionInfo["parameters"][string];

const isBasicType = (type: string): boolean => {
  const basicTypes = [
    "str",
    "string",
    "int",
    "integer",
    "number",
    "float",
    "bool",
    "boolean",
    "list",
    "List",
    "dict",
    "Dict",
  ];
  if (basicTypes.includes(type)) return true;
  const listMatch = type.match(/^List\[(.*)\]$/);
  if (listMatch) return isBasicType(listMatch[1]);
  const dictMatch = type.match(/^Dict\[(.*),(.*)\]$/);
  if (dictMatch)
    return isBasicType(dictMatch[1].trim()) && isBasicType(dictMatch[2].trim());
  return false;
};

const parseValue = (value: any, type: string): any => {
  if (value === null || value === undefined || value === "") return null;
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
      case "list":
      case "List":
        if (typeof value === "string")
          return value
            .split(",")
            .map((v) => v.trim())
            .filter(Boolean);
        return Array.isArray(value) ? value : [value];
      case "dict":
      case "Dict":
        if (typeof value === "string") {
          try {
            return JSON.parse(value);
          } catch {
            return {};
          }
        }
        return value;
      default:
        const listMatch = type.match(/^List\[(.*)\]$/);
        if (listMatch) {
          const itemType = listMatch[1];
          if (typeof value === "string") {
            return value
              .split(",")
              .map((v) => v.trim())
              .filter(Boolean)
              .map((v) => parseValue(v, itemType));
          }
          return Array.isArray(value)
            ? value.map((v) => parseValue(v, itemType))
            : [parseValue(value, itemType)]; // ensure single value is also parsed if wrapped in array
        }
        return value; // For other complex types, return as is or consider deeper parsing if needed.
    }
  } catch (error) {
    console.error(`Error parsing value ${value} as type ${type}:`, error);
    return null;
  }
};

export default function RunFunction() {
  const [selectedFunctionPath, setSelectedFunctionPath] = useState<string>("");
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [parameters, setParameters] = useState<Record<string, any>>({});
  const [logs, setLogs] = useState<string[]>([]);
  const [isRunningTask, setIsRunningTask] = useState(false);
  const [currentJobId, setCurrentJobId] = useState<string | null>(null);
  const eventSourceCleanupRef = useRef<(() => void) | null>(null);

  // 1. Fetch available functions
  const {
    data: availableFunctionsData,
    isLoading: isLoadingFunctions,
    isError: isErrorFunctions,
    error: functionsError,
  } = useAvailableFunctions();

  // Map API data to FunctionUI type for the dropdown
  const functionsForUI: FunctionUI[] =
    availableFunctionsData?.map((func: FunctionInfo) => ({
      ...func, // Spread raw API data
      path: func.full_path,
      name: func.function_name,
      module: func.module_name,
      parameters: Object.entries(func.parameters).reduce(
        (acc, [key, value]) => {
          const paramInfo = value as ApiParameterInfo; // Type assertion for API param structure
          acc[key] = {
            required: paramInfo.required || false,
            default: paramInfo.default,
            type: paramInfo.type || "string", // API should provide type
            description: paramInfo.description,
          };
          return acc;
        },
        {} as Record<string, FunctionParameterUI>,
      ),
    })) || [];

  // 2. Fetch info for the selected function (dependent query)
  const {
    data: selectedFunctionInfoData,
    isLoading: isLoadingFunctionInfo,
    isError: isErrorFunctionInfo,
    error: functionInfoError,
  } = useFunctionInfo(selectedFunctionPath);

  // Map API data to FunctionUI type for displaying details
  const functionInfoForUI: FunctionUI | null = selectedFunctionInfoData
    ? {
        ...(selectedFunctionInfoData as FunctionInfo), // Use FunctionInfo
        path: selectedFunctionInfoData.full_path,
        name: selectedFunctionInfoData.function_name,
        module: selectedFunctionInfoData.module_name,
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

  const runFunctionMutation = useRunFunctionMutation();

  // useEffect to initialize parameters when functionInfoForUI changes
  useEffect(() => {
    if (functionInfoForUI) {
      const defaultParams = Object.entries(functionInfoForUI.parameters).reduce(
        (acc, [key, info]) => ({
          ...acc,
          // Use actual default value if present, otherwise null or appropriate empty state based on type
          [key]:
            info.default !== undefined
              ? info.default
              : info.type === "bool" || info.type === "boolean"
                ? false
                : "",
        }),
        {},
      );
      setParameters(defaultParams);
      setLogs([]);
      setCurrentJobId(null);
      setIsRunningTask(false);
      if (eventSourceCleanupRef.current) {
        eventSourceCleanupRef.current();
        eventSourceCleanupRef.current = null;
      }
    } else {
      setParameters({});
      setLogs([]);
      if (eventSourceCleanupRef.current) {
        eventSourceCleanupRef.current();
        eventSourceCleanupRef.current = null;
      }
    }
    return () => {
      if (eventSourceCleanupRef.current) {
        eventSourceCleanupRef.current();
        eventSourceCleanupRef.current = null;
      }
    };
  }, [functionInfoForUI]); // Depend on the mapped UI version

  const updateParameter = (name: string, value: any) => {
    setParameters((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!functionInfoForUI) return;

    // Close existing event source if any before starting a new task
    if (eventSourceCleanupRef.current) {
      eventSourceCleanupRef.current();
      eventSourceCleanupRef.current = null;
    }
    setLogs([]);
    setIsRunningTask(true);
    setCurrentJobId(null);

    const parsedParams = Object.entries(parameters).reduce(
      (acc, [key, value]) => {
        const paramInfo = functionInfoForUI.parameters[key];
        if (!paramInfo) return acc;
        const parsed = parseValue(value, paramInfo.type);
        if (parsed !== null || !paramInfo.required) {
          acc[key] = parsed;
        } else if (paramInfo.required && parsed === null) {
          acc[key] = null;
        }
        return acc;
      },
      {} as Record<string, any>,
    );

    try {
      const response = await runFunctionMutation.mutateAsync({
        functionPath: functionInfoForUI.full_path,
        parameters: parsedParams,
      });

      // API returns `queue_id`, let's assume it's the job ID for logs
      const newJobId = response.queue_id;
      setCurrentJobId(newJobId);
      toast({ title: "Task Submitted", description: `Job ID: ${newJobId}` });

      // Setup EventSource for logs using subscribeToJobLogs
      eventSourceCleanupRef.current = subscribeToJobLogs(
        apiClient,
        newJobId,
        (message) => {
          // onMessage
          try {
            const logData = JSON.parse(message);
            setLogs((prev) => [...prev, logData.message || message]);
            if (
              logData.message &&
              typeof logData.message === "string" &&
              (logData.message.includes(`Job ${newJobId} completed`) ||
                logData.message.includes(`Job ${newJobId} failed`)) // Check for completion or failure
            ) {
              setIsRunningTask(false);
              if (eventSourceCleanupRef.current) {
                eventSourceCleanupRef.current();
                eventSourceCleanupRef.current = null;
              }
              toast({
                title: logData.message.includes("completed")
                  ? "Task Completed"
                  : "Task Failed",
                description: `Job ${newJobId} finished. Status: ${logData.message.includes("completed") ? "Completed" : "Failed"}`,
              });
            }
          } catch (parseError) {
            setLogs((prev) => [...prev, message]);
          }
        },
        (err) => {
          // onError
          console.error("Log stream error:", err);
          setLogs((prev) => [...prev, "Error in log stream or stream closed."]);
          toast({ title: "Log Stream Error", variant: "destructive" });
          setIsRunningTask(false);
          if (eventSourceCleanupRef.current) {
            eventSourceCleanupRef.current();
            eventSourceCleanupRef.current = null;
          }
        },
        () => {
          // onComplete
          setIsRunningTask(false);
          if (
            !logs.some(
              (log) =>
                log.includes(`Job ${newJobId} completed`) ||
                log.includes(`Job ${newJobId} failed`),
            )
          ) {
            toast({
              title: "Log Stream Ended",
              description: `Job ${newJobId} log stream closed.`,
            });
          }
          if (eventSourceCleanupRef.current) {
            eventSourceCleanupRef.current();
            eventSourceCleanupRef.current = null;
          }
        },
      );
    } catch (error: any) {
      console.error("Failed to submit task:", error);
      setIsRunningTask(false);
    }
  };

  const renderParameterField = (name: string, info: FunctionParameterUI) => {
    const paramId = `param-${name}`;
    const value = parameters[name];

    if (info.type === "bool" || info.type === "boolean") {
      return (
        <div key={name} className="mb-4 items-center">
          <div className="flex items-center space-x-2">
            <input
              type="checkbox"
              id={paramId}
              checked={Boolean(value)}
              onChange={(e) => updateParameter(name, e.target.checked)}
              className="h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
            />
            <Label htmlFor={paramId} className="flex flex-col">
              <span>
                {name}
                {info.required && " *"}{" "}
                <span className="text-xs text-gray-500">({info.type})</span>
              </span>
              {info.description && (
                <span className="text-xs font-normal text-gray-400">
                  {info.description}
                </span>
              )}
            </Label>
          </div>
        </div>
      );
    }
    return (
      <div key={name} className="mb-4">
        <Label htmlFor={paramId} className="block text-sm font-medium">
          {name}
          {info.required && " *"}{" "}
          <span className="text-xs text-gray-500">({info.type})</span>
          {info.description && (
            <p className="mt-1 text-xs font-normal text-gray-400">
              {info.description}
            </p>
          )}
        </Label>
        <Input
          id={paramId}
          type={
            info.type === "int" ||
            info.type === "integer" ||
            info.type === "float" ||
            info.type === "number"
              ? "number"
              : "text"
          }
          value={value === null || value === undefined ? "" : String(value)} // Handle null/undefined for input value
          onChange={(e) => updateParameter(name, e.target.value)} // Raw value, parsing happens on submit
          placeholder={`Default: ${info.default !== undefined ? String(info.default) : info.required ? "Required" : "Optional"}`}
          className="mt-1"
        />
      </div>
    );
  };

  if (isLoadingFunctions) return <p>Loading available functions...</p>;
  if (isErrorFunctions)
    return <p>Error loading functions: {functionsError?.message}</p>;

  return (
    <Card className="p-6">
      <div className="mb-4">
        <Label>Select Function</Label>
        <Popover open={open} onOpenChange={setOpen}>
          <PopoverTrigger asChild>
            <Button
              variant="outline"
              role="combobox"
              aria-expanded={open}
              className="w-full justify-between truncate"
              disabled={isLoadingFunctionInfo || isRunningTask}
            >
              {selectedFunctionPath
                ? functionsForUI.find(
                    (func) => func.full_path === selectedFunctionPath,
                  )?.name
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
                        value={func.full_path} // Use full_path as the value
                        onSelect={(currentValue) => {
                          setSelectedFunctionPath(
                            currentValue === selectedFunctionPath
                              ? ""
                              : currentValue,
                          );
                          setOpen(false);
                          setSearch("");
                        }}
                        className="truncate"
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
      {isErrorFunctionInfo && (
        <p>Error loading function details: {functionInfoError?.message}</p>
      )}

      {functionInfoForUI && (
        <form onSubmit={handleSubmit}>
          <Title className="mb-2 text-lg">
            Parameters for {functionInfoForUI.name}
          </Title>
          {functionInfoForUI.doc && (
            <p className="mb-4 text-sm text-gray-500 italic">
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
          <Button
            type="submit"
            disabled={
              isRunningTask ||
              isLoadingFunctionInfo ||
              runFunctionMutation.isPending
            }
            className="mt-4"
          >
            {isRunningTask
              ? `Running (Job ID: ${currentJobId})...`
              : runFunctionMutation.isPending
                ? "Submitting Task..."
                : "Run Task"}
          </Button>
        </form>
      )}

      {logs.length > 0 && (
        <div className="mt-6">
          <Title className="mb-2 text-lg">Logs</Title>
          <ScrollArea className="bg-muted h-[200px] w-full rounded-md border p-4">
            {logs.map((log, index) => (
              <pre
                key={index}
                className="text-xs break-all whitespace-pre-wrap"
              >
                {log}
              </pre>
            ))}
          </ScrollArea>
        </div>
      )}
    </Card>
  );
}
