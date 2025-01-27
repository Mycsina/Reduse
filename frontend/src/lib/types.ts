export enum AnalysisStatus {
  PENDING = 'pending',
  IN_PROGRESS = 'in_progress',
  COMPLETED = 'completed',
  FAILED = 'failed',
}

export interface Listing {
  _id: string;
  title: string;
  description: string;
  price_value: number;
  site: string;
  analysis_status: AnalysisStatus;
  original_id: string;
  photo_urls: string[];
}

export interface AnalyzedListing {
  id: string;
  original_listing_id: string;
  type: string | null;
  brand: string | null;
  base_model: string | null;
  model_variant: string | null;
  info: Record<string, any>;
}

export interface AnalysisStatusResponse {
  total: number;
  completed: number;
  pending: number;
  failed: number;
  in_progress: number;
  max_retries_reached: number;
  can_process: boolean;
}

export interface ModelAnalytics {
  brand: string;
  base_model: string;
  avg_price: number | null;
  min_price: number | null;
  max_price: number | null;
  median_price: number | null;
  count: number;
  timestamp: string;
}

export interface FilterCondition {
  field: string;
  pattern: string;
}

export interface FilterGroup {
  type: 'AND' | 'OR';
  conditions: (FilterCondition | FilterGroup)[];
}

export interface ListingQuery {
  // Basic filters
  price?: {
    min?: number;
    max?: number;
  };
  site?: string;
  status?: AnalysisStatus;
  search_text?: string;

  // Advanced filters
  filter?: FilterGroup;
  
  // Analysis fields to include
  include_fields?: string[];
  
  // Similarity search
  similar_to?: string;  // listing ID to find similar items
  
  // Raw query for direct MongoDB queries
  raw_query?: Record<string, any>;
  
  // Pagination
  skip?: number;
  limit?: number;
}

export interface ListingResponse {
  listing: Listing;
  analysis: AnalyzedListing | null;
}
