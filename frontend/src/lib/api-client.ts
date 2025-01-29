import { ListingQuery } from '@/lib/types';

interface ScheduleConfig {
  job_id?: string;
  cron?: string;
  interval_seconds?: number;
  enabled?: boolean;
  max_instances?: number;
}

// Add missing types
interface AnalysisStatusType {
  pending: number;
  in_progress: number;
  failed: number;
  completed: number;
  can_process: boolean;
}

// Add ModelPriceStats interface to match backend schema
interface ModelPriceStats {
  model: string;
  avg_price: number;
  min_price: number;
  max_price: number;
  median_price: number;
  sample_size: number;
  timestamp: string;
}

class APIClient {
  private apiKey: string;
  private baseUrl: string;
  private cache: Map<string, { data: any; timestamp: number }> = new Map();
  private CACHE_TTL = 5 * 60 * 1000; // 5 minutes

  // API endpoint paths
  private endpoints = {
    query: '/query',
    listings: '/listings',
    analysis: '/analysis',
    scrape: '/scrape',
    schedule: '/schedule',
    analytics: '/analytics',
  };

  constructor() {
    this.baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    this.apiKey = process.env.NEXT_PUBLIC_API_KEY || '1234567890';
  }

  // Cache management
  private getCacheKey(endpoint: string, options: RequestInit = {}): string {
    return `${endpoint}:${JSON.stringify(options.body)}`;
  }

  private setCache(key: string, data: any) {
    this.cache.set(key, { data, timestamp: Date.now() });
  }

  private getCache(key: string): any | null {
    const cached = this.cache.get(key);
    if (!cached) return null;
    if (Date.now() - cached.timestamp > this.CACHE_TTL) {
      this.cache.delete(key);
      return null;
    }
    return cached.data;
  }

  getApiKey(): string {
    return this.apiKey;
  }

  // Base fetch method
  private async fetch(endpoint: string, options: RequestInit = {}) {
    const cacheKey = this.getCacheKey(endpoint, options);
    
    if (options.method === undefined || options.method === 'GET') {
      const cached = this.getCache(cacheKey);
      if (cached) return cached;
    }

    const response = await fetch(`${this.baseUrl}${endpoint}`, {
      ...options,
      headers: {
        ...options.headers,
        'Content-Type': 'application/json',
        'X-API-Key': this.apiKey,
      },
    });

    if (!response.ok) {
      throw new Error(`API Error: ${response.statusText}`);
    }

    const data = await response.json();
    
    if (options.method === undefined || options.method === 'GET') {
      this.setCache(cacheKey, data);
    }

    return data;
  }

  // Analytics endpoints
  async getCurrentModelStats(baseModel: string): Promise<ModelPriceStats | null> {
    if (!baseModel) return null;
    return this.fetch(`${this.endpoints.analytics}/current/${baseModel}`);
  }

  async getModelPriceHistory(
    baseModel: string,
    days: number = 30,
    limit?: number
  ): Promise<ModelPriceStats[]> {
    if (!baseModel) return [];
    const params = new URLSearchParams();
    if (days) params.append('days', days.toString());
    if (limit) params.append('limit', limit.toString());
    return this.fetch(`${this.endpoints.analytics}/history/${baseModel}?${params}`);
  }

  async updatePriceStats(): Promise<{ message: string }> {
    return this.fetch(`${this.endpoints.analytics}/update-stats`, { method: 'POST' });
  }

  // Query endpoints
  async queryListings(query: ListingQuery = {}) {
    return this.fetch(`${this.endpoints.query}${this.endpoints.listings}`, {
      method: 'POST',
      body: JSON.stringify(query),
    });
  }

  async getAvailableFields() {
    return this.fetch(`${this.endpoints.query}${this.endpoints.listings}/fields`);
  }

  // Analysis endpoints
  async getAnalysisStatus() {
    return this.fetch(`${this.endpoints.analysis}/status`) as Promise<AnalysisStatusType>;
  }

  async startAnalysis() {
    return this.fetch(`${this.endpoints.analysis}/start`, { method: 'POST' });
  }

  async retryFailedAnalyses() {
    return this.fetch(`${this.endpoints.analysis}/retry-failed`, { method: 'POST' });
  }

  async resumeAnalysis() {
    return this.fetch(`${this.endpoints.analysis}/resume`, { method: 'POST' });
  }

  async cancelAnalysis() {
    return this.fetch(`${this.endpoints.analysis}/cancel`, { method: 'POST' });
  }

  async regenerateEmbeddings() {
    return this.fetch(`${this.endpoints.analysis}/regenerate-embeddings`, { method: 'POST' });
  }

  // Query endpoints
  async getSimilarListings(listingId: string, includeFields?: string[], skip = 0, limit = 12) {
    return this.fetch(`${this.endpoints.query}${this.endpoints.listings}/similar/${listingId}`, {
      method: 'POST',
      body: JSON.stringify({ include_fields: includeFields, skip, limit }),
    });
  }

  async getListing(id: string) {
    return this.fetch(`${this.endpoints.query}${this.endpoints.listings}/by_id/${id}`);
  }

  // Scraping endpoints
  async scrapeUrl(url: string) {
    return this.fetch(`${this.endpoints.scrape}`, {
      method: 'POST',
      body: JSON.stringify({ url }),
    });
  }

  async scrapeOlxCategories() {
    return this.fetch(`${this.endpoints.scrape}/olx`, { method: 'POST' });
  }

  subscribeToLogs(queueId: string, onMessage: (message: string) => void, onError?: (error: any) => void, onComplete?: () => void) {
    const url = new URL(`${this.baseUrl}${this.endpoints.scrape}/logs/${queueId}`);
    return this.createEventSource(url, onMessage, onError, onComplete);
  }

  // Scheduling endpoints
  async getScheduledJobs() {
    return this.fetch(`${this.endpoints.schedule}/jobs`);
  }

  async getAvailableFunctions() {
    return this.fetch(`${this.endpoints.schedule}/functions`);
  }

  async getFunctionInfo(functionPath: string) {
    return this.fetch(`${this.endpoints.schedule}/functions/${functionPath}`);
  }

  async scheduleFunction(functionPath: string, config: ScheduleConfig) {
    return this.fetch(`${this.endpoints.schedule}/functions/schedule`, {
      method: 'POST',
      body: JSON.stringify({
        function_path: functionPath,
        config,
      }),
    });
  }

  async runFunction(functionPath: string, config: { parameters?: Record<string, any> }) {
    return this.fetch(`${this.endpoints.schedule}/functions/run`, {
      method: 'POST',
      body: JSON.stringify({
        function_path: functionPath,
        parameters: config.parameters,
      }),
    });
  }

  async getJobStatus(jobId: string) {
    return this.fetch(`${this.endpoints.schedule}/jobs/${jobId}/status`);
  }

  subscribeToJobLogs(
    jobId: string,
    onMessage: (message: string) => void,
    onError?: (error: any) => void,
    onComplete?: () => void
  ) {
    const url = new URL(`${this.baseUrl}${this.endpoints.schedule}/jobs/${jobId}/logs`);
    url.searchParams.append('min_level', 'INFO');
    return this.createFetchStream(url, onMessage, onError, onComplete);
  }

  // Job management
  async pauseScheduledJob(jobId: string) {
    return this.fetch(`${this.endpoints.schedule}/jobs/${jobId}/pause`, { method: 'PUT' });
  }

  async resumeScheduledJob(jobId: string) {
    return this.fetch(`${this.endpoints.schedule}/jobs/${jobId}/resume`, { method: 'PUT' });
  }

  async deleteScheduledJob(jobId: string) {
    return this.fetch(`${this.endpoints.schedule}/jobs/${jobId}`, { method: 'DELETE' });
  }

  // Utility methods for streaming
  private createEventSource(
    url: URL,
    onMessage: (message: string) => void,
    onError?: (error: any) => void,
    onComplete?: () => void
  ) {
    let retryCount = 0;
    const MAX_RETRIES = 3;
    const RETRY_DELAY = 3000;
    let eventSource: EventSource | null = null;

    const connect = () => {
      if (eventSource) {
        eventSource.close();
      }

      eventSource = new EventSource(url.toString());

      eventSource.onopen = () => {
        retryCount = 0;
      };

      eventSource.onmessage = (event) => {
        try {
          if (!event.data) return;
          const message = JSON.parse(event.data);
          onMessage(event.data);
        } catch (error) {
          if (onError) onError(error);
        }
      };

      eventSource.onerror = (error) => {
        if (eventSource?.readyState === EventSource.CLOSED) {
          if (retryCount < MAX_RETRIES) {
            retryCount++;
            setTimeout(connect, RETRY_DELAY);
          } else {
            cleanup();
          }
        }
        if (onError) onError(error);
      };
    };

    const cleanup = () => {
      if (eventSource) {
        eventSource.close();
        eventSource = null;
      }
      if (onComplete) onComplete();
    };

    connect();
    return cleanup;
  }

  private createFetchStream(
    url: URL,
    onMessage: (message: string) => void,
    onError?: (error: any) => void,
    onComplete?: () => void
  ) {
    let retryCount = 0;
    const MAX_RETRIES = 3;
    const RETRY_DELAY = 3000;
    let abortController = new AbortController();

    const connect = async () => {
      try {
        const response = await fetch(url.toString(), {
          headers: {
            'X-API-Key': this.apiKey,
            'Accept': 'text/event-stream',
          },
          signal: abortController.signal
        });

        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }

        const reader = response.body?.getReader();
        if (!reader) {
          throw new Error('No reader available');
        }

        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          
          if (done) {
            if (onComplete) onComplete();
            break;
          }

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';
          
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const data = line.slice(6);
                onMessage(data);
              } catch (error) {
                console.error('Error parsing message:', error);
              }
            }
          }
        }
      } catch (error: unknown) {
        if (error instanceof Error && error.name === 'AbortError') {
          return;
        }
        
        if (retryCount < MAX_RETRIES) {
          retryCount++;
          setTimeout(connect, RETRY_DELAY);
        } else if (onError) {
          onError(error);
        }
      }
    };

    connect();
    return () => {
      abortController.abort();
      abortController = new AbortController();
    };
  }
}

export const apiClient = new APIClient();

