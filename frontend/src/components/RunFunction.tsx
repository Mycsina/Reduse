"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { apiClient } from "@/lib/api-client";
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

interface ParameterInfo {
  required: boolean;
  default: any;
  type: string;
  description: string | null;
}

interface Function {
  path: string;
  name: string;
  module: string;
  doc: string;
  is_async: boolean;
  parameters: Record<string, ParameterInfo>;
  return_type: string;
}

// Add type parsing utilities
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

  // Check if it's a basic type or a list/dict of basic types
  if (basicTypes.includes(type)) return true;

  // Check for List[basic_type] or Dict[basic_type, basic_type]
  const listMatch = type.match(/^List\[(.*)\]$/);
  if (listMatch) {
    return isBasicType(listMatch[1]);
  }

  const dictMatch = type.match(/^Dict\[(.*),(.*)\]$/);
  if (dictMatch) {
    return isBasicType(dictMatch[1].trim()) && isBasicType(dictMatch[2].trim());
  }

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
        if (typeof value === "string") {
          return value.toLowerCase() === "true";
        }
        return Boolean(value);

      case "list":
      case "List":
        if (typeof value === "string") {
          return value
            .split(",")
            .map((v) => v.trim())
            .filter(Boolean);
        }
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
        // Handle List[type] and Dict[type, type]
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
            : [value];
        }

        // For now, return the value as-is for other types
        return value;
    }
  } catch (error) {
    console.error(`Error parsing value ${value} as type ${type}:`, error);
    return null;
  }
};

export default function RunFunction() {
  const [functions, setFunctions] = useState<Function[]>([]);
  const [selectedFunction, setSelectedFunction] = useState<string>("");
  const [functionInfo, setFunctionInfo] = useState<Function | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [parameters, setParameters] = useState<Record<string, any>>({});
  const [logs, setLogs] = useState<string[]>([]);
  const [isRunning, setIsRunning] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);

  useEffect(() => {
    fetchFunctions();
  }, []);

  useEffect(() => {
    if (selectedFunction) {
      fetchFunctionInfo(selectedFunction);
    } else {
      setFunctionInfo(null);
    }
  }, [selectedFunction]);

  useEffect(() => {
    if (functionInfo) {
      // Initialize parameters with default values
      const defaultParams = Object.entries(functionInfo.parameters).reduce(
        (acc, [key, info]) => ({
          ...acc,
          [key]: info.default ?? null,
        }),
        {}
      );
      setParameters(defaultParams);
    }
  }, [functionInfo]);

  const fetchFunctions = async () => {
    try {
      const response = await apiClient.getAvailableFunctions();
      setFunctions(response.functions);
    } catch (error) {
      toast({
        title: "Failed to fetch functions",
        description:
          error instanceof Error ? error.message : "Unknown error occurred",
        variant: "destructive",
      });
    }
  };

  const fetchFunctionInfo = async (path: string) => {
    try {
      const info = await apiClient.getFunctionInfo(path);
      setFunctionInfo(info);
    } catch (error) {
      toast({
        title: "Failed to fetch function info",
        description:
          error instanceof Error ? error.message : "Unknown error occurred",
        variant: "destructive",
      });
    }
  };

  const updateParameter = (name: string, value: any) => {
    setParameters((prev) => ({
      ...prev,
      [name]: value,
    }));
  };

  const filteredFunctions = functions.filter((func) => {
    if (!search) return true;

    // First check if all parameters are of basic types
    const hasComplexTypes = Object.values(func.parameters).some(
      (param) => !isBasicType(param.type)
    );

    if (hasComplexTypes) return false;

    const searchLower = search.toLowerCase();
    return (
      (func.name?.toLowerCase()?.includes(searchLower) ?? false) ||
      (func.module?.toLowerCase()?.includes(searchLower) ?? false) ||
      (func.doc?.toLowerCase()?.includes(searchLower) ?? false)
    );
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFunction) {
      toast({
        title: "Please select a function",
        variant: "destructive",
      });
      return;
    }

    try {
      setIsLoading(true);
      setIsRunning(true);
      setLogs([]);

      // Parse parameters according to their types
      const parsedParameters = Object.entries(parameters).reduce(
        (acc, [key, value]) => {
          const paramInfo = functionInfo?.parameters[key];
          if (!paramInfo) return acc;

          const parsedValue = parseValue(value, paramInfo.type);
          if (parsedValue !== null) {
            acc[key] = parsedValue;
          }
          return acc;
        },
        {} as Record<string, any>
      );

      const response = await apiClient.runFunction(selectedFunction, {
        parameters: parsedParameters,
      });

      setJobId(response.job_id);

      // Subscribe to logs
      const cleanup = apiClient.subscribeToJobLogs(
        response.job_id,
        (log) => {
          try {
            const logData = JSON.parse(log);
            setLogs((prev) => [...prev, logData.message]);

            // Check for completion message
            if (
              logData.message ===
              `Job ${response.job_id} completed successfully`
            ) {
              cleanup();
              setIsRunning(false);
              setJobId(null);
              toast({
                title: "Function completed successfully",
              });
            }
          } catch (error) {
            console.error("Failed to parse log:", error);
          }
        },
        (error) => {
          console.error("Log stream error:", error);
          toast({
            title: "Error streaming logs",
            description: String(error),
            variant: "destructive",
          });
        },
        () => {
          setIsRunning(false);
          setJobId(null);
        }
      );

      // Cleanup subscription when component unmounts or on error
      return () => cleanup();
    } catch (error) {
      toast({
        title: "Failed to run function",
        description:
          error instanceof Error ? error.message : "Unknown error occurred",
        variant: "destructive",
      });
      setIsRunning(false);
      setJobId(null);
    } finally {
      setIsLoading(false);
    }
  };

  const renderParameterField = (name: string, info: ParameterInfo) => {
    // Don't render fields for complex types
    if (!isBasicType(info.type)) {
      return null;
    }

    const value = parameters[name];
    const label = `${name}${info.required ? " *" : ""}`;

    switch (info.type.toLowerCase()) {
      case "bool":
      case "boolean":
        return (
          <div key={name} className="flex items-center space-x-2">
            <input
              type="checkbox"
              id={name}
              checked={value ?? false}
              onChange={(e) => updateParameter(name, e.target.checked)}
              className="h-4 w-4 rounded border-gray-300"
            />
            <Label htmlFor={name}>
              {label}
              {info.description && (
                <span className="text-sm text-muted-foreground ml-2">
                  ({info.description})
                </span>
              )}
            </Label>
          </div>
        );

      case "int":
      case "integer":
      case "float":
      case "number":
        return (
          <div key={name} className="space-y-2">
            <Label htmlFor={name}>
              {label}
              {info.description && (
                <span className="text-sm text-muted-foreground ml-2">
                  ({info.description})
                </span>
              )}
            </Label>
            <Input
              id={name}
              type="number"
              value={value ?? ""}
              onChange={(e) => updateParameter(name, e.target.value)}
              required={info.required}
              step={info.type.toLowerCase().includes("float") ? "any" : "1"}
            />
          </div>
        );

      case "list":
      case "array":
        return (
          <div key={name} className="space-y-2">
            <Label htmlFor={name}>
              {label}
              {info.description && (
                <span className="text-sm text-muted-foreground ml-2">
                  ({info.description})
                </span>
              )}
            </Label>
            <Input
              id={name}
              value={Array.isArray(value) ? value.join(", ") : value ?? ""}
              onChange={(e) => updateParameter(name, e.target.value)}
              placeholder="Comma-separated values"
              required={info.required}
            />
          </div>
        );

      case "dict":
      case "object":
        return (
          <div key={name} className="space-y-2">
            <Label htmlFor={name}>
              {label}
              {info.description && (
                <span className="text-sm text-muted-foreground ml-2">
                  ({info.description})
                </span>
              )}
            </Label>
            <Input
              id={name}
              value={
                typeof value === "object" ? JSON.stringify(value) : value ?? ""
              }
              onChange={(e) => {
                try {
                  const parsed = JSON.parse(e.target.value);
                  updateParameter(name, parsed);
                } catch {
                  updateParameter(name, e.target.value);
                }
              }}
              placeholder="JSON object"
              required={info.required}
            />
          </div>
        );

      default: // string or any other type
        return (
          <div key={name} className="space-y-2">
            <Label htmlFor={name}>
              {label}
              {info.description && (
                <span className="text-sm text-muted-foreground ml-2">
                  ({info.description})
                </span>
              )}
            </Label>
            <Input
              id={name}
              value={value ?? ""}
              onChange={(e) => updateParameter(name, e.target.value)}
              required={info.required}
            />
          </div>
        );
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div className="space-y-2">
        <Label>Function</Label>
        <Popover open={open} onOpenChange={setOpen}>
          <PopoverTrigger asChild>
            <Button
              variant="outline"
              role="combobox"
              aria-expanded={open}
              className="w-full justify-between"
            >
              {selectedFunction
                ? functions.find((f) => f.path === selectedFunction)?.name ||
                  "Select function"
                : "Select function"}
              <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
            </Button>
          </PopoverTrigger>
          <PopoverContent className="w-[400px] p-0" align="start">
            <Command>
              <CommandInput
                placeholder="Search functions..."
                value={search}
                onValueChange={setSearch}
              />
              <CommandList>
                <CommandEmpty>No functions found.</CommandEmpty>
                <CommandGroup>
                  {filteredFunctions.map((func) => (
                    <CommandItem
                      key={func.path}
                      value={func.path}
                      onSelect={(value) => {
                        setSelectedFunction(value);
                        setOpen(false);
                      }}
                    >
                      <Check
                        className={cn(
                          "mr-2 h-4 w-4",
                          selectedFunction === func.path
                            ? "opacity-100"
                            : "opacity-0"
                        )}
                      />
                      <div className="flex flex-col">
                        <span>{func.name}</span>
                        <span className="text-sm text-muted-foreground">
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

      {functionInfo && (
        <>
          <Card className="p-4 space-y-2">
            <h3 className="font-semibold">{functionInfo.name}</h3>
            <p className="text-sm text-muted-foreground">{functionInfo.doc}</p>
            <div className="text-sm">
              <p>
                <strong>Module:</strong> {functionInfo.module}
              </p>
              <p>
                <strong>Return Type:</strong> {functionInfo.return_type}
              </p>
              <p>
                <strong>Async:</strong> {functionInfo.is_async ? "Yes" : "No"}
              </p>
            </div>
          </Card>

          {Object.keys(functionInfo.parameters).length > 0 && (
            <Card className="p-4 space-y-4">
              <h3 className="font-semibold">Parameters</h3>
              {Object.entries(functionInfo.parameters).map(([name, info]) =>
                renderParameterField(name, info)
              )}
            </Card>
          )}
        </>
      )}

      <Button
        type="submit"
        className="w-full"
        disabled={isLoading || !selectedFunction || isRunning}
      >
        {isRunning ? "Running..." : "Run Function"}
      </Button>

      {logs.length > 0 && (
        <Card className="p-4">
          <h3 className="font-semibold mb-2">Logs</h3>
          <ScrollArea className="h-[200px] w-full rounded-md border p-4">
            {logs.map((log, index) => (
              <div key={index} className="font-mono text-sm">
                {log}
              </div>
            ))}
          </ScrollArea>
        </Card>
      )}
    </form>
  );
}
