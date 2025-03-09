/* tslint:disable */
/* eslint-disable */
/**
/* This file was automatically generated from pydantic models by running pydantic2ts.
/* Do not modify it by hand - just update the pydantic models and then re-run the script
*/

/**
 * Type of filter group.
 */
export type FilterGroupType = "AND" | "OR";
export type AnalysisStatus1 = "pending" | "in_progress" | "completed" | "failed";

/**
 * Schedule configuration for analysis tasks.
 */
export interface AnalysisSchedule {
  /**
   * Optional job ID. If not provided, one will be generated.
   */
  job_id?: string | null;
  cron?: string | null;
  interval_seconds?: number | null;
  start_date?: string | null;
  end_date?: string | null;
  enabled?: boolean;
  max_instances?: number;
  retry_failed?: boolean;
  reanalyze_all?: boolean;
  regenerate_embeddings?: boolean;
}
export interface AnalysisStatus {
  total: number;
  completed: number;
  pending: number;
  failed: number;
  in_progress: number;
  max_retries_reached: number;
  can_process?: boolean;
}
/**
 * Request model for creating a task from a function.
 */
export interface CreateTaskRequest {
  function_path: string;
  config: TaskConfig;
}
/**
 * Base configuration for scheduled tasks.
 */
export interface TaskConfig {
  /**
   * Optional job ID. If not provided, one will be generated.
   */
  job_id?: string | null;
  cron?: string | null;
  interval_seconds?: number | null;
  max_instances?: number;
  enabled?: boolean;
  /**
   * Parameters to pass to the task function
   */
  parameters?: {
    [k: string]: unknown;
  };
  [k: string]: unknown;
}
/**
 * Response model for function information.
 */
export interface FunctionInfoResponse {
  name: string;
  description: string;
  parameters: {
    [k: string]: unknown;
  };
  required: string[];
}
/**
 * Response model for available functions listing.
 */
export interface FunctionListResponse {
  functions: string[];
}
/**
 * Response model for health check endpoint.
 */
export interface HealthCheckResponse {
  status: "healthy" | "unhealthy";
  timestamp: number;
  duration_ms: number;
  checks: ServiceCheck[];
}
/**
 * Model for individual service health check.
 */
export interface ServiceCheck {
  name: string;
  status: "healthy" | "unhealthy";
  duration_ms?: number | null;
  error?: string | null;
}
/**
 * Response model for job listing.
 */
export interface JobListResponse {
  jobs: {
    [k: string]: unknown;
  }[];
}
/**
 * Response model for job status.
 */
export interface JobStatusResponse {
  job_id: string;
  status: string;
  next_run_time?: string | null;
  runs: {
    [k: string]: unknown;
  }[];
}
/**
 * Query model for standard listing queries.
 */
export interface ListingQuery {
  price?: PriceFilter | null;
  search_text?: string | null;
  filter?: FilterGroup | null;
  skip?: number;
  limit?: number;
}
/**
 * Price filter model.
 */
export interface PriceFilter {
  min?: number | null;
  max?: number | null;
}
/**
 * Model for a group of filter conditions.
 */
export interface FilterGroup {
  type: FilterGroupType;
  conditions: (FilterCondition | FilterGroup)[];
  [k: string]: unknown;
}
/**
 * Model for a single filter condition.
 */
export interface FilterCondition {
  field: string;
  pattern: string;
  [k: string]: unknown;
}
/**
 * Response model for listing queries.
 */
export interface ListingResponse {
  listing: ListingDocument;
  analysis: AnalyzedListingDocument | null;
}
/**
 * Schema for product listings.
 *
 * This schema stores the raw listing data as scraped from various sources.
 * Fields are populated in two stages:
 * 1. Basic info from listing cards (always populated)
 * 2. Details (description, location) from individual listing pages (optional)
 */
export interface ListingDocument {
  /**
   * MongoDB document ObjectID
   */
  _id?: string | null;
  original_id: string;
  site: string;
  title: string;
  link: string;
  price_str: string;
  price_value: string | null;
  photo_urls?: string[];
  description: string | null;
  more?: boolean;
  analysis_status?: AnalysisStatus1;
  analysis_error?: string | null;
  retry_count?: number;
  analysis_status_retry_count?: null;
  analysis_status_price?: null;
  site_timestamp?: null;
  [k: string]: unknown;
}
/**
 * Schema for analyzed listings.
 *
 * This schema stores the results of product analysis, including:
 * 1. Core product identification (type, brand, base model, variant)
 * 2. Additional product information (specs, condition, etc.)
 * 3. Analysis metadata (version, retry count)
 * 4. Vector embeddings for similarity search
 */
export interface AnalyzedListingDocument {
  /**
   * MongoDB document ObjectID
   */
  _id?: string | null;
  parsed_listing_id: string | null;
  original_listing_id: string;
  type?: string | null;
  brand?: string | null;
  base_model?: string | null;
  model_variant?: string | null;
  info?: {
    [k: string]: unknown;
  };
  embeddings?: number[] | null;
  analysis_version: string;
  retry_count?: number;
  [k: string]: unknown;
}
/**
 * Schedule configuration for maintenance tasks.
 */
export interface MaintenanceSchedule {
  /**
   * Optional job ID. If not provided, one will be generated.
   */
  job_id?: string | null;
  cron?: string | null;
  interval_seconds?: number | null;
  start_date?: string | null;
  end_date?: string | null;
  enabled?: boolean;
  max_instances?: number;
  cleanup_old_logs?: boolean;
  vacuum_database?: boolean;
  update_indexes?: boolean;
}
/**
 * Response model for metrics endpoint.
 */
export interface MetricsResponse {
  timestamp: number;
  system: SystemMetrics;
}
/**
 * Model for system uptime metrics.
 */
export interface SystemMetrics {
  uptime?: number;
}
/**
 * Document for storing model price statistics.
 */
export interface ModelPriceStats {
  /**
   * MongoDB document ObjectID
   */
  _id?: string | null;
  base_model: string;
  avg_price: string;
  min_price: string;
  max_price: string;
  median_price: string;
  sample_size: number;
  timestamp?: string;
  /**
   * List of model variants included in this group
   */
  variants?: string[];
}
/**
 * Schedule configuration for OLX category scraping tasks.
 */
export interface OLXScrapeSchedule {
  /**
   * Optional job ID. If not provided, one will be generated.
   */
  job_id?: string | null;
  cron?: string | null;
  interval_seconds?: number | null;
  start_date?: string | null;
  end_date?: string | null;
  enabled?: boolean;
  max_instances?: number;
  analyze?: boolean;
  generate_embeddings?: boolean;
  categories?: string[] | null;
}
/**
 * Response model for endpoints that start a background task.
 */
export interface QueuedTaskResponse {
  message: string;
  queue_id: string;
}
/**
 * Request model for running a function once.
 */
export interface RunFunctionRequest {
  function_path: string;
  parameters?: {
    [k: string]: unknown;
  } | null;
}
/**
 * Base model for schedule configuration.
 */
export interface ScheduleBase {
  /**
   * Optional job ID. If not provided, one will be generated.
   */
  job_id?: string | null;
  cron?: string | null;
  interval_seconds?: number | null;
  start_date?: string | null;
  end_date?: string | null;
  enabled?: boolean;
  max_instances?: number;
}
/**
 * Response model for scheduling endpoints.
 */
export interface ScheduleResponse {
  message: string;
  job_id: string;
  config: {
    [k: string]: unknown;
  };
}
/**
 * Request model for scraping a URL.
 */
export interface ScrapeRequest {
  url: string;
}
/**
 * Schedule configuration for URL-based scraping tasks.
 */
export interface ScrapeSchedule {
  /**
   * Optional job ID. If not provided, one will be generated.
   */
  job_id?: string | null;
  cron?: string | null;
  interval_seconds?: number | null;
  start_date?: string | null;
  end_date?: string | null;
  enabled?: boolean;
  max_instances?: number;
  urls: string[];
  analyze?: boolean;
  generate_embeddings?: boolean;
}
/**
 * Simple response for job operations.
 */
export interface SimpleJobResponse {
  message: string;
  job_id: string;
}
/**
 * Response model for update stats endpoint.
 */
export interface UpdateStatsResponse {
  message: string;
}
