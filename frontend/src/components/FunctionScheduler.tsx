"use client";

import { useState, useEffect, useRef } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { CronSelector } from "@/components/ui/cronSelector";
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

export default function FunctionScheduler() {
  const [functions, setFunctions] = useState<Function[]>([]);
  const [selectedFunction, setSelectedFunction] = useState<string>("");
  const [functionInfo, setFunctionInfo] = useState<Function | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [config, setConfig] = useState({
    cron: "0 0 * * *", // Default daily at midnight
    enabled: true,
    max_instances: 1,
    parameters: {} as Record<string, any>,
  });
  const [isHovered, setIsHovered] = useState(false);
  const buttonRef = useRef<HTMLButtonElement>(null);

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
      setConfig((prev) => ({
        ...prev,
        parameters: defaultParams,
      }));
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
    setConfig((prev) => ({
      ...prev,
      parameters: {
        ...prev.parameters,
        [name]: value,
      },
    }));
  };

  const renderParameterField = (name: string, info: ParameterInfo) => {
    const value = config.parameters[name];
    const label = `${name}${info.required ? " *" : ""}`;

    switch (info.type.toLowerCase()) {
      case "boolean":
        return (
          <div
            key={name}
            className="flex items-center justify-between space-x-2"
          >
            <Label htmlFor={name} className="flex-grow">
              {label}
              {info.description && (
                <span className="text-sm text-muted-foreground ml-2">
                  ({info.description})
                </span>
              )}
            </Label>
            <Switch
              id={name}
              checked={value ?? false}
              onCheckedChange={(checked) => updateParameter(name, checked)}
            />
          </div>
        );

      case "number":
      case "integer":
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
              onChange={(e) => updateParameter(name, Number(e.target.value))}
              required={info.required}
            />
          </div>
        );

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
              value={Array.isArray(value) ? value.join(", ") : ""}
              onChange={(e) =>
                updateParameter(
                  name,
                  e.target.value.split(",").map((s) => s.trim())
                )
              }
              placeholder="Comma-separated values"
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
      await apiClient.scheduleFunction(selectedFunction, {
        parameters: Object.fromEntries(
          Object.entries(config.parameters).filter(
            ([_, value]) => value != null
          )
        )
      });
      toast({ title: "Function scheduled successfully" });
      setSelectedFunction("");
      setConfig({
        cron: "0 0 * * *",
        enabled: true,
        max_instances: 1,
        parameters: {},
      });
    } catch (error) {
      toast({
        title: "Failed to schedule function",
        description:
          error instanceof Error ? error.message : "Unknown error occurred",
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  };

  const filteredFunctions = functions.filter((func) => {
    if (!search) return true;
    const searchLower = search.toLowerCase();
    return (
      (func.name?.toLowerCase()?.includes(searchLower) ?? false) ||
      (func.module?.toLowerCase()?.includes(searchLower) ?? false) ||
      (func.doc?.toLowerCase()?.includes(searchLower) ?? false)
    );
  });

  const handleWheel = (e: WheelEvent) => {
    if (!isHovered || !functions.length) return;

    e.preventDefault();

    const currentIndex = selectedFunction
      ? functions.findIndex((f) => f.path === selectedFunction)
      : -1;

    let newIndex;
    if (e.deltaY > 0) {
      // Scrolling down
      newIndex =
        currentIndex === -1 || currentIndex === functions.length - 1
          ? 0
          : currentIndex + 1;
    } else {
      // Scrolling up
      newIndex =
        currentIndex === -1 || currentIndex === 0
          ? functions.length - 1
          : currentIndex - 1;
    }

    setSelectedFunction(functions[newIndex].path);
  };

  useEffect(() => {
    const button = buttonRef.current;
    if (!button) return;

    const handleWheelEvent = (e: WheelEvent) => handleWheel(e);

    if (isHovered) {
      button.addEventListener("wheel", handleWheelEvent, { passive: false });
    }

    return () => {
      button.removeEventListener("wheel", handleWheelEvent);
    };
  }, [isHovered, selectedFunction, functions]);

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div className="space-y-2">
        <Label>Function</Label>
        <Popover open={open} onOpenChange={setOpen}>
          <PopoverTrigger asChild>
            <Button
              ref={buttonRef}
              variant="outline"
              role="combobox"
              aria-expanded={open}
              className="w-full justify-between"
              onMouseEnter={() => setIsHovered(true)}
              onMouseLeave={() => setIsHovered(false)}
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

      <div className="space-y-2">
        <Label>Schedule</Label>
        <CronSelector
          value={config.cron}
          onChange={(value) => setConfig({ ...config, cron: value })}
        />
      </div>

      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <Label>Enabled</Label>
          <Switch
            checked={config.enabled}
            onCheckedChange={(checked) =>
              setConfig({ ...config, enabled: checked })
            }
          />
        </div>

        <div className="flex items-center space-x-2">
          <Label>Max Instances</Label>
          <Input
            type="number"
            min={1}
            max={10}
            value={config.max_instances}
            onChange={(e) =>
              setConfig({ ...config, max_instances: parseInt(e.target.value) })
            }
            className="w-20"
          />
        </div>
      </div>

      <Button
        type="submit"
        className="w-full"
        disabled={isLoading || !selectedFunction}
      >
        Schedule Function
      </Button>
    </form>
  );
}
