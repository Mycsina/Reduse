import { AnalysisStatus, ListingQuery, ListingResponse, AnalysisStatusResponse, ModelAnalytics } from '@/lib/types';

class APIClient {
  private apiKey: string;
  private baseUrl: string;
  private cache: Map<string, { data: any; timestamp: number }> = new Map();
  private CACHE_TTL = 5 * 60 * 1000; // 5 minutes

  constructor() {
    this.baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    this.apiKey = process.env.NEXT_PUBLIC_API_KEY || '1234567890';
  }

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

  private query = '/query';
  private listings = '/listings';
  private analysis = '/analysis';
  private scrape = '/scrape';
  private schedule = '/schedule';

  private async fetch(endpoint: string, options: RequestInit = {}) {
    const cacheKey = this.getCacheKey(endpoint, options);
    
    // Only cache GET requests
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
    
    // Cache the response for GET requests
    if (options.method === undefined || options.method === 'GET') {
      this.setCache(cacheKey, data);
    }

    return data;
  }

  // Listings endpoints
  async queryListings(query: ListingQuery = {}) {
    return this.fetch(this.query + this.listings, {
      method: 'POST',
      body: JSON.stringify(query),
    }) as Promise<ListingResponse[]>;
  }

  async getSimilarListings(listingId: string, includeFields?: string[], skip = 0, limit = 12) {
    return this.fetch(this.query + this.listings + `/similar/${listingId}`, {
      method: 'POST',
      body: JSON.stringify({ include_fields: includeFields, skip, limit }),
    }) as Promise<ListingResponse[]>;
  }

  async queryListingsRaw(query: Record<string, any>, skip = 0, limit = 12) {
    return this.fetch(this.query + this.listings + '/raw', {
      method: 'POST',
      body: JSON.stringify({ query, skip, limit }),
    }) as Promise<ListingResponse[]>;
  }

  async getListing(id: string) {
    return this.fetch(this.query + this.listings + `/by_id/${id}`) as Promise<ListingResponse>;
  }

  // Analysis endpoints
  async getAnalysisStatus() {
    return this.fetch(this.analysis + '/status') as Promise<AnalysisStatusResponse>;
  }

  async startAnalysis() {
    return this.fetch(this.analysis + '/start', { method: 'POST' }) as Promise<void>;
  }

  async retryFailedAnalyses() {
    return this.fetch(this.analysis + '/retry-failed', { method: 'POST' }) as Promise<void>;
  }

  async resumeAnalysis() {
    return this.fetch(this.analysis + '/resume', { method: 'POST' }) as Promise<void>;
  }

  async reanalyzeListings() {
    return this.fetch(this.analysis + '/reanalyze', { method: 'POST' }) as Promise<void>;
  }

  async regenerateEmbeddings() {
    return this.fetch(this.analysis + '/regenerate-embeddings', { method: 'POST' }) as Promise<void>;
  }

  async cancelAnalysis() {
    return this.fetch(this.analysis + '/cancel', { method: 'POST' }) as Promise<void>;
  }

  // Scraping endpoints
  async scrapeUrl(url: string) {
    return this.fetch(this.scrape, {
      method: 'POST',
      body: JSON.stringify({ url }),
    }) as Promise<{ message: string; queue_id: string }>;
  }

  async scrapeOlxCategories() {
    return this.fetch(this.scrape + '/olx', { 
      method: 'POST' 
    }) as Promise<{ message: string; queue_id: string }>;
  }

  // Logging endpoints
  subscribeToLogs(queueId: string, onMessage: (message: string) => void, onError?: (error: any) => void, onComplete?: () => void) {
    const url = new URL(`${this.baseUrl}${this.scrape}/logs/${queueId}`);
    url.searchParams.append('api_key', this.apiKey);
    
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
          if (!event.data) {
            return;
          }

          const message = JSON.parse(event.data);

          switch (message.type) {
            case 'connected':
              break;
            case 'error':
              if (onError) onError(message.data);
              break;
            case 'disconnected':
            case 'done':
              cleanup();
              if (message.type === 'done' && onComplete) onComplete();
              break;
            default:
              onMessage(event.data);
          }
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
        
        if (onError) {
          onError(error);
        }
      };
    };

    const cleanup = () => {
      if (eventSource) {
        eventSource.close();
        eventSource = null;
      }
      if (onComplete) {
        onComplete();
      }
    };

    connect();
    return cleanup;
  }

  // Stats endpoints
  async updatePriceStats(): Promise<{ message: string }> {
    return this.fetch(this.analysis + '/update-stats', { method: 'POST' }) as Promise<{ message: string }>;
  }

  async getAvailableFields(): Promise<{ main_fields: string[]; info_fields: string[]; }> {
    return this.fetch(this.query + this.listings + '/fields') as Promise<{ main_fields: string[]; info_fields: string[]; }>;
  }

  async getModelAnalytics(base_model: string): Promise<ModelAnalytics[]> {
    return this.fetch(this.query + this.listings + `/models?base_model=${base_model}`) as Promise<ModelAnalytics[]>;
  }
}

export const apiClient = new APIClient();

