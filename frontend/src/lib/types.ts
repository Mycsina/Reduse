// Re-export all types from the API types file
export * from "../types/api";

// Add any additional types needed by the application below

// Define AnalysisStatus as both a type and an enum-like object
export type AnalysisStatus = "pending" | "in_progress" | "completed" | "failed";

export const AnalysisStatus = {
  PENDING: "pending" as AnalysisStatus,
  IN_PROGRESS: "in_progress" as AnalysisStatus,
  COMPLETED: "completed" as AnalysisStatus,
  FAILED: "failed" as AnalysisStatus,
};

// AnalyzedListing type alias for backward compatibility
export type AnalyzedListing = import("../types/api").AnalyzedListingDocument;

export interface Listing {
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
  analysis_status?: AnalysisStatus;
  analysis_error?: string | null;
  retry_count?: number;
  [key: string]: any;
}

export interface ModelAnalytics {
  model: string;
  count: number;
  avgPrice: number;
  minPrice: number;
  maxPrice: number;
}

export interface FilterCondition {
  field: string;
  operator: string;
  value: string;
}

export interface FilterGroup {
  type: "AND" | "OR";
  conditions: (FilterCondition | FilterGroup)[];
} 