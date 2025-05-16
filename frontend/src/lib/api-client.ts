// Define the base class with core logic
class APIClient {
  baseUrl: string;

  constructor() {
    this.baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
  }

  async _fetch(endpoint: string, options: RequestInit = {}) {
    const response = await fetch(`${this.baseUrl}${endpoint}`, {
      ...options,
      credentials: 'include',
      headers: {
        ...options.headers,
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      let errorData;
      try {
        errorData = await response.json();
      } catch (e) {
        errorData = { detail: response.statusText };
      }
      const error = new Error(errorData?.detail || `HTTP error! status: ${response.status}`);
      (error as any).status = response.status;
      (error as any).data = errorData;
      throw error;
    }

    if (response.status === 204) return null;

    const data = await response.json();
    // if (options.method === undefined || options.method === 'GET' && useCache) {
    //   this.setCache(cacheKey, data);
    // }
    return data;
  }

  // Utility methods for streaming
  createEventSource(
    urlPath: string, onMessage: (message: string) => void,
    onError?: (error: any) => void, onComplete?: () => void
  ): () => void {
    let retryCount = 0, MAX_RETRIES = 3, RETRY_DELAY = 3000;
    let eventSource: EventSource | null = null;
    const fullUrl = new URL(`${this.baseUrl}${urlPath}`);
    console.warn("EventSource used: Ensure authentication is handled (e.g., via cookies) as custom headers are not supported.");
    const connect = () => {
      if (eventSource) eventSource.close();
      console.log(`Connecting EventSource to: ${fullUrl.toString()}`);
      eventSource = new EventSource(fullUrl.toString());
      eventSource.onopen = () => { console.log(`EventSource connected: ${urlPath}`); retryCount = 0; };
      eventSource.onmessage = (event) => { try { if (event.data) onMessage(event.data); } catch (e) { console.error(`Error parsing EventSource message from ${urlPath}:`, e); if (onError) onError(e); } };
      eventSource.onerror = (error) => {
        console.error(`EventSource error for ${urlPath}:`, error);
        if (eventSource?.readyState === EventSource.CLOSED) {
          console.log(`EventSource closed for ${urlPath}. Attempting reconnect #${retryCount + 1}...`);
          if (retryCount < MAX_RETRIES) {
            retryCount++; setTimeout(connect, RETRY_DELAY * Math.pow(2, retryCount - 1));
          } else {
            console.error(`EventSource failed after ${MAX_RETRIES} retries for ${urlPath}. No more retries.`);
            cleanup();
            if (onError) onError(new Error(`EventSource failed after ${MAX_RETRIES} retries.`));
          }
        } else if (onError) onError(error);
      };
    };
    const cleanup = () => { if (eventSource) { console.log(`Closing EventSource: ${urlPath}`); eventSource.close(); eventSource = null; } if (onComplete) onComplete(); };
    connect(); return cleanup;
  }
  createFetchStream(
    urlPath: string, onMessage: (message: string) => void,
    onError?: (error: any) => void, onComplete?: () => void
  ): () => void {
    let retryCount = 0;
    const MAX_RETRIES = 3, RETRY_DELAY = 3000;
    let abortController: AbortController;
    const fullUrl = new URL(`${this.baseUrl}${urlPath}`);
    const connect = async () => {
      abortController = new AbortController();
      console.log(`Connecting FetchStream to: ${fullUrl.toString()}`);
      try {
        const response = await fetch(fullUrl.toString(), { headers: { 'Accept': 'text/event-stream' }, signal: abortController.signal });
        if (!response.ok) { const e = new Error(`HTTP error! status: ${response.status}`); (e as any).status = response.status; throw e; }
        const reader = response.body?.getReader(); if (!reader) throw new Error('Failed to get stream reader');
        console.log(`FetchStream connected: ${urlPath}`); retryCount = 0;
        const decoder = new TextDecoder(); let buffer = '';
        while (true) {
          const { done, value } = await reader.read(); if (done) { console.log(`FetchStream completed: ${urlPath}`); if (onComplete) onComplete(); break; }
          buffer += decoder.decode(value, { stream: true }); const lines = buffer.split('\n'); buffer = lines.pop() || '';
          for (const line of lines) {
            if (line.startsWith('data: ')) { try { const data = line.slice(6).trim(); if (data) onMessage(data); } catch (e) { console.error(`Error processing FetchStream message:`, e, "Raw:", line); } }
            // Other SSE lines handling (event, id, retry) can be added if needed
          }
        }
      } catch (error: unknown) {
        console.error(`FetchStream error (${urlPath}):`, error);
        if (error instanceof Error && error.name === 'AbortError') { console.log(`FetchStream aborted: ${urlPath}`); return; }
        const status = (error as any)?.status; const shouldRetry = !status || status >= 500;
        if (shouldRetry && retryCount < MAX_RETRIES) {
          retryCount++; console.log(`Retrying FetchStream (${urlPath}) attempt ${retryCount}...`); setTimeout(connect, RETRY_DELAY * Math.pow(2, retryCount - 1));
        } else {
          console.error(`FetchStream failed permanently or was aborted for ${urlPath}.`); if (onError) onError(error);
        }
      }
    };
    connect(); return () => { console.log(`Aborting FetchStream: ${urlPath}`); abortController.abort(); };
  }
}

// Export the base class *before* creating the instance
export { APIClient };

// Create the singleton instance
const apiClient = new APIClient();

export default apiClient;
