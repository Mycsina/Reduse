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
import { apiClient } from "@/lib/api-client";

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

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    try {
      let response;
      const { jobType, config } = formData;

      switch (jobType) {
        case "scrape":
          response = await apiClient.scheduleUrlScraping({
            ...config,
            urls: config.urls?.filter((url) => url) || [],
          });
          break;
        case "olx_scrape":
          response = await apiClient.scheduleOlxScraping(config);
          break;
        case "analysis":
          response = await apiClient.scheduleAnalysis(config);
          break;
        case "maintenance":
          response = await apiClient.scheduleMaintenance(config);
          break;
        default:
          toast({ title: "Please select a job type", variant: "destructive" });
          return;
      }

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

  const updateConfig = (updates: Partial<typeof formData.config>) => {
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

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div className="space-y-2">
        <Label>Job Type</Label>
        <Select
          onValueChange={(value: JobType | "") =>
            setFormData({ ...formData, jobType: value })
          }
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

      <Button type="submit" className="w-full">
        Create Schedule
      </Button>
    </form>
  );
}
