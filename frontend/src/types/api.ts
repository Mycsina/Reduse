/* eslint-disable */

// --- Enums --- //

/**
 * Type of filter group.
 */
export type FilterGroupType = "AND" | "OR";

/**
 * Operator for filter conditions.
 */
export type OperatorType =
  | "EQUALS"
  | "CONTAINS"
  | "REGEX"
  | "GT"
  | "LT"
  | "GTE"
  | "LTE"
  | "EQ_NUM";

/**
 * Status of listing analysis (used in ListingDocument).
 */
export type ListingAnalysisStatusType = "pending" | "in_progress" | "completed" | "failed";

/**
 * Status of a bug report.
 */
export enum BugReportStatus {
  OPEN = "open",
  REVIEWED = "reviewed",
  RESOLVED = "resolved",
  INVALID = "invalid",
}

/**
 * Type of bug report.
 */
export enum BugReportType {
  INCORRECT_DATA = "incorrect_data",
  MISSING_DATA = "missing_data",
  WRONG_ANALYSIS = "wrong_analysis",
  DUPLICATE_LISTING = "duplicate_listing", // Added based on user request, check if backend supports
  OTHER = "other",
}


// --- Query & Filtering --- //

/**
 * Price filter model.
 */
export interface PriceFilter {
  min?: number | null;
  max?: number | null;
}

/**
 * Model for a single filter condition.
 */
export interface FilterCondition {
  field: string;
  operator: OperatorType; // Use OperatorType enum
  value: string;         // Changed from pattern
}

/**
 * Model for a group of filter conditions.
 */
export interface FilterGroup {
  type: FilterGroupType;
  conditions: (FilterCondition | FilterGroup)[];
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

// --- Listings & Analysis --- //

/**
 * Schema for product listings (as received by frontend).
 */
export interface ListingDocument {
  _id?: string | null; // Beanie/Mongo ID
  original_id: string;
  site: string;
  title: string;
  link?: string | null; // Was HttpUrl, now string
  price_str: string;
  price_value: number | null; // Corrected from string
  photo_urls?: string[];     // Was List[HttpUrl]
  description?: string | null;
  more?: boolean;
  analysis_status?: ListingAnalysisStatusType;
  analysis_error?: string | null;
  retry_count?: number;
  timestamp?: string; // Add timestamp if needed from backend
  // parameters?: Record<string, string> | null; // If used from backend schema
  // created_at?: string; // If needed
  // updated_at?: string; // If needed
}

/**
 * Schema for analyzed listings (as received by frontend).
 */
export interface AnalyzedListingDocument {
  _id?: string | null; // Beanie/Mongo ID
  // parsed_listing_id: string | null; // Seems unused in client/routers
  original_listing_id: string;
  type?: string | null;
  brand?: string | null;
  base_model?: string | null;
  model_variant?: string | null;
  info?: Record<string, any>; // Changed from unknown
  embeddings?: number[] | null;
  analysis_version?: string;
  retry_count?: number;
  // created_at?: string; // If needed
  // updated_at?: string; // If needed
}

/**
 * Response model for listing queries.
 */
export interface ListingResponse {
  listing: ListingDocument;
  analysis: AnalyzedListingDocument | null;
}

/**
 * Overall analysis status summary.
 */
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
 * Response for analysis status-changing actions.
 */
export interface AnalysisStatusResponse {
  message: string;
  can_retry?: boolean | null;
  can_start?: boolean | null;
  can_resume?: boolean | null;
  total?: number | null;
  completed?: number | null;
  pending?: number | null;
  failed?: number | null;
  in_progress?: number | null;
  max_retries_reached?: number | null;
}

/**
 * Response for cancelling analysis.
 */
export interface CancelAnalysisResponse {
  message: string;
  cancelled: number;
}


// --- Analytics --- //

/**
 * Document for storing model price statistics.
 */
export interface ModelPriceStats {
  _id?: string | null; // Beanie/Mongo ID
  base_model: string;
  avg_price: string; // Stored as string in backend schema
  min_price: string; // Stored as string in backend schema
  max_price: string; // Stored as string in backend schema
  median_price: string; // Stored as string in backend schema
  sample_size: number;
  timestamp?: string; // Changed from datetime
  variants?: string[];
}

/**
 * Response model for update stats endpoint.
 */
export interface UpdateStatsResponse {
  message: string;
}

/**
 * Response model for getting available filter fields.
 */
export interface InfoFieldsResponse {
  main_fields: string[];
  info_fields: string[];
}


// --- Tasks & Scheduling --- //

/**
 * Base configuration for scheduled tasks.
 */
export interface TaskConfig {
  job_id?: string | null;
  cron?: string | null;
  interval_seconds?: number | null;
  max_instances?: number;
  enabled?: boolean;
  parameters?: Record<string, any>;
}

/**
 * Request model for creating a task from a function.
 */
export interface CreateTaskRequest {
  function_path: string;
  config: TaskConfig;
}

/**
 * Request model for running a function once.
 */
export interface RunFunctionRequest {
  function_path: string;
  parameters?: Record<string, any> | null;
}

/**
 * Information about a discovered function.
 */
export interface FunctionInfo {
  module_name: string;
  function_name: string;
  full_path: string;
  doc: string | null;
  is_async: boolean;
  parameters: Record<string, Record<string, any>>;
  return_type: string | null;
}

/**
 * Response model for scheduling endpoints.
 */
export interface ScheduleResponse {
  message: string;
  job_id: string;
  config: Record<string, any>;
}

/**
 * Simple response for job operations.
 */
export interface SimpleJobResponse {
  message: string;
  job_id: string;
}

/**
 * Response model for endpoints that start a background task.
 */
export interface QueuedTaskResponse {
  message: string;
  queue_id: string;
}

/**
 * Status of a running job.
 */
export interface JobStatus {
  job_id: string;
  status: string; // e.g., 'running', 'completed', 'failed'
  result?: any;   // Changed from unknown
  error?: string | null;
}


// --- Bug Reports --- //

/**
 * Schema for creating a bug report.
 */
export interface BugReportCreate {
  listing_id: string;
  original_id: string;
  site: string;
  report_type: BugReportType;
  description: string;
  incorrect_fields?: Record<string, any> | null;
  expected_values?: Record<string, any> | null;
}

/**
 * Response schema for bug reports.
 */
export interface BugReportResponse {
  id: string;
  listing_id: string;
  report_type: BugReportType;
  description: string;
  status: BugReportStatus;
  timestamp: string; // Changed from datetime
}
