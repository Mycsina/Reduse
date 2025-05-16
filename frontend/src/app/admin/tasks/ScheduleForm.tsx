"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { CronSelector } from "@/components/ui/cronSelector";
import { toast } from "@/hooks/use-toast";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";

import {
  useScheduleFunctionMutation,
  type TaskConfig,
} from "@/lib/api/admin/tasks";

type JobType = "scrape" | "olx_scrape" | "analysis" | "maintenance";

interface BaseScheduleConfig {
  job_id?: string;
  cron: string;
  interval_seconds?: number;
  enabled: boolean;
  max_instances: number;
}

interface ScrapeConfig extends BaseScheduleConfig {
  urls: string[];
  analyze: boolean;
  generate_embeddings: boolean;
}

interface OLXScrapeConfig extends BaseScheduleConfig {
  analyze: boolean;
  generate_embeddings: boolean;
  categories?: string[];
}

interface AnalysisConfig extends BaseScheduleConfig {
  retry_failed: boolean;
  reanalyze_all: boolean;
  regenerate_embeddings: boolean;
}

interface MaintenanceConfig extends BaseScheduleConfig {
  cleanup_old_logs: boolean;
  vacuum_database: boolean;
  update_indexes: boolean;
}

type ConfigByType = {
  scrape: ScrapeConfig;
  olx_scrape: OLXScrapeConfig;
  analysis: AnalysisConfig;
  maintenance: MaintenanceConfig;
};

type FormConfig = {
  cron: string;
  enabled: boolean;
  max_instances: number;
  urls?: string[];
  analyze?: boolean;
  generate_embeddings?: boolean;
  retry_failed?: boolean;
  reanalyze_all?: boolean;
  regenerate_embeddings?: boolean;
  cleanup_old_logs?: boolean;
  vacuum_database?: boolean;
  update_indexes?: boolean;
};

export default function ScheduleForm() {
  const [formData, setFormData] = useState<{
    jobType: JobType | "";
    config: FormConfig;
  }>({
    jobType: "",
    config: {
      cron: "0 0 * * *", // Default daily at midnight
      enabled: true,
      max_instances: 1,
      urls: [""],
      analyze: true,
      generate_embeddings: true,
    },
  });

  const router = useRouter();

  const scheduleFunctionMutation = useScheduleFunctionMutation();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    const { jobType, config } = formData;
    if (!jobType) {
      toast({ title: "Please select a job type", variant: "destructive" });
      return;
    }

    let functionPath: string;
    let taskParameters: Record<string, any> = {};

    switch (jobType) {
      case "scrape":
        functionPath = "app.tasks.predefined.url_scraping";
        taskParameters = {
          urls: config.urls?.filter((url) => !!url) || [],
          analyze: !!config.analyze,
          generate_embeddings: !!config.generate_embeddings,
        };
        break;
      case "olx_scrape":
        functionPath = "app.tasks.predefined.olx_scraping";
        taskParameters = {
          analyze: !!config.analyze,
          generate_embeddings: !!config.generate_embeddings,
        };
        break;
      case "analysis":
        functionPath = "app.tasks.predefined.analysis_job";
        taskParameters = {
          retry_failed: !!config.retry_failed,
          reanalyze_all: !!config.reanalyze_all,
          regenerate_embeddings: !!config.regenerate_embeddings,
        };
        break;
      case "maintenance":
        functionPath = "app.tasks.predefined.maintenance_job";
        taskParameters = {
          cleanup_old_logs: !!config.cleanup_old_logs,
          vacuum_database: !!config.vacuum_database,
          update_indexes: !!config.update_indexes,
        };
        break;
      default:
        toast({ title: "Invalid job type selected", variant: "destructive" });
        return;
    }

    try {
      const taskConfig: TaskConfig = {
        cron: config.cron,
        enabled: config.enabled,
        max_instances: config.max_instances,
        parameters: taskParameters,
      };

      await scheduleFunctionMutation.mutateAsync({
        functionPath,
        config: taskConfig,
      });

      toast({ title: "Schedule created successfully" });
      router.refresh();
    } catch (error) {
      toast({
        title: "Failed to create schedule",
        description:
          error instanceof Error ? error.message : "Unknown error occurred",
        variant: "destructive",
      });
    }
  };

  const updateConfig = (updates: Partial<FormConfig>) => {
    setFormData((prev) => ({
      ...prev,
      config: { ...prev.config, ...updates },
    }));
  };

  const addUrlField = () => {
    const urls = formData.config.urls || [];
    updateConfig({ urls: [...urls, ""] });
  };

  const updateUrl = (index: number, value: string) => {
    const urls = [...(formData.config.urls || [])];
    urls[index] = value;
    updateConfig({ urls });
  };

  const removeUrl = (index: number) => {
    const urls = [...(formData.config.urls || [])];
    urls.splice(index, 1);
    updateConfig({ urls });
  };

  const isLoading = scheduleFunctionMutation.isPending;

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div className="space-y-2">
        <Label>Job Type</Label>
        <Select
          value={formData.jobType}
          onValueChange={(value: JobType | "") => {
            const baseConfig: FormConfig = {
              cron: "0 0 * * *",
              enabled: true,
              max_instances: 1,
            };
            let jobSpecificConfig: Partial<FormConfig> = {};

            if (value === "scrape") {
              jobSpecificConfig = {
                urls: [""],
                analyze: true,
                generate_embeddings: true,
              };
            } else if (value === "olx_scrape") {
              jobSpecificConfig = {
                analyze: true,
                generate_embeddings: true,
              };
            } else if (value === "analysis") {
              jobSpecificConfig = {
                retry_failed: false,
                reanalyze_all: false,
                regenerate_embeddings: false,
              };
            } else if (value === "maintenance") {
              jobSpecificConfig = {
                cleanup_old_logs: true,
                vacuum_database: false,
                update_indexes: false,
              };
            }

            setFormData({
              jobType: value,
              config: { ...baseConfig, ...jobSpecificConfig } as FormConfig,
            });
          }}
        >
          <SelectTrigger>
            <SelectValue placeholder="Select job type" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="scrape">URL Scraping</SelectItem>
            <SelectItem value="olx_scrape">OLX Category Scraping</SelectItem>
            <SelectItem value="analysis">Analysis</SelectItem>
            <SelectItem value="maintenance">Maintenance</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {formData.jobType === "scrape" && (
        <div className="space-y-4">
          <Label>URLs to Scrape</Label>
          {(formData.config.urls || []).map((url, index) => (
            <div key={index} className="flex space-x-2">
              <Input
                type="url"
                placeholder="URL to scrape"
                value={url}
                onChange={(e) => updateUrl(index, e.target.value)}
              />
              <Button
                type="button"
                variant="outline"
                onClick={() => removeUrl(index)}
              >
                Remove
              </Button>
            </div>
          ))}
          <Button
            type="button"
            variant="outline"
            onClick={addUrlField}
            className="w-full"
          >
            Add URL
          </Button>

          <div className="space-y-2">
            <div className="flex items-center space-x-2">
              <Checkbox
                id="analyze"
                checked={formData.config.analyze}
                onCheckedChange={(checked: boolean) =>
                  updateConfig({ analyze: checked })
                }
              />
              <Label htmlFor="analyze">Analyze scraped listings</Label>
            </div>

            <div className="flex items-center space-x-2">
              <Checkbox
                id="generate_embeddings"
                checked={formData.config.generate_embeddings}
                onCheckedChange={(checked: boolean) =>
                  updateConfig({ generate_embeddings: checked })
                }
              />
              <Label htmlFor="generate_embeddings">Generate embeddings</Label>
            </div>
          </div>
        </div>
      )}

      {formData.jobType === "olx_scrape" && (
        <div className="space-y-4">
          <div className="flex items-center space-x-2">
            <Checkbox
              id="analyze_olx"
              checked={formData.config.analyze}
              onCheckedChange={(checked: boolean) =>
                updateConfig({ analyze: checked })
              }
            />
            <Label htmlFor="analyze_olx">Analyze scraped listings</Label>
          </div>

          <div className="flex items-center space-x-2">
            <Checkbox
              id="generate_embeddings_olx"
              checked={formData.config.generate_embeddings}
              onCheckedChange={(checked: boolean) =>
                updateConfig({ generate_embeddings: checked })
              }
            />
            <Label htmlFor="generate_embeddings_olx">Generate embeddings</Label>
          </div>
        </div>
      )}

      {formData.jobType === "analysis" && (
        <div className="space-y-4">
          <div className="flex items-center space-x-2">
            <Checkbox
              id="retry_failed"
              checked={formData.config.retry_failed}
              onCheckedChange={(checked: boolean) =>
                updateConfig({ retry_failed: checked })
              }
            />
            <Label htmlFor="retry_failed">Retry failed analyses</Label>
          </div>

          <div className="flex items-center space-x-2">
            <Checkbox
              id="reanalyze_all"
              checked={formData.config.reanalyze_all}
              onCheckedChange={(checked: boolean) =>
                updateConfig({ reanalyze_all: checked })
              }
            />
            <Label htmlFor="reanalyze_all">Reanalyze all listings</Label>
          </div>

          <div className="flex items-center space-x-2">
            <Checkbox
              id="regenerate_embeddings"
              checked={formData.config.regenerate_embeddings}
              onCheckedChange={(checked: boolean) =>
                updateConfig({ regenerate_embeddings: checked })
              }
            />
            <Label htmlFor="regenerate_embeddings">Regenerate embeddings</Label>
          </div>
        </div>
      )}

      {formData.jobType === "maintenance" && (
        <div className="space-y-4">
          <div className="flex items-center space-x-2">
            <Checkbox
              id="cleanup_old_logs"
              checked={formData.config.cleanup_old_logs}
              onCheckedChange={(checked: boolean) =>
                updateConfig({ cleanup_old_logs: checked })
              }
            />
            <Label htmlFor="cleanup_old_logs">Clean up old logs</Label>
          </div>

          <div className="flex items-center space-x-2">
            <Checkbox
              id="vacuum_database"
              checked={formData.config.vacuum_database}
              onCheckedChange={(checked: boolean) =>
                updateConfig({ vacuum_database: checked })
              }
            />
            <Label htmlFor="vacuum_database">Vacuum database</Label>
          </div>

          <div className="flex items-center space-x-2">
            <Checkbox
              id="update_indexes"
              checked={formData.config.update_indexes}
              onCheckedChange={(checked: boolean) =>
                updateConfig({ update_indexes: checked })
              }
            />
            <Label htmlFor="update_indexes">Update indexes</Label>
          </div>
        </div>
      )}

      <div className="space-y-2">
        <Label>Schedule</Label>
        <CronSelector
          value={formData.config.cron || ""}
          onChange={(value) => updateConfig({ cron: value })}
        />
      </div>

      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <Label>Enabled</Label>
          <Switch
            checked={formData.config.enabled}
            onCheckedChange={(checked: boolean) =>
              updateConfig({ enabled: checked })
            }
          />
        </div>

        <div className="flex items-center space-x-2">
          <Label>Max Instances</Label>
          <Input
            type="number"
            min={1}
            max={10}
            value={formData.config.max_instances}
            onChange={(e) =>
              updateConfig({ max_instances: parseInt(e.target.value) })
            }
            className="w-20"
          />
        </div>
      </div>

      <Button
        type="submit"
        className="w-full"
        disabled={isLoading || !formData.jobType}
      >
        {isLoading ? "Scheduling..." : "Schedule Job"}
      </Button>
    </form>
  );
}
