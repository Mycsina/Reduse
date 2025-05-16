import { APIClient } from '@/lib/api-client';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import apiClient from '@/lib/api-client';
import { useToast } from '@/hooks/use-toast';

// Define base paths locally
const tasksBasePath = '/admin/tasks';
const schedulePath = '/schedule';
const functionsPath = '/functions';

const TASKS_QUERY_KEY_PREFIX = 'tasks';

// Assuming these types are defined elsewhere or should be more generic
// For now, using 'any' as placeholder if specific types aren't available here.
export interface JobListResponse extends Array<any> {} // Placeholder
export interface FunctionInfoResponse extends Record<string, any> {} // Placeholder
export interface QueuedTaskResponse { // Already defined in scrape.ts, re-declaring for clarity or import if shared
    message: string;
    queue_id: string; 
}
export interface SimpleJobResponse { // Already defined in analysis.ts, re-declaring for clarity or import if shared
    message: string;
    job_id: string;
}


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
 * Status of a running job.
 */
export interface JobStatusResponse {
  job_id: string;
  status: string; // e.g., 'running', 'completed', 'failed'
  result?: any;   // Changed from unknown
  error?: string | null;
}

// --- Query Hooks ---
export function useScheduledJobs() {
  return useQuery<JobListResponse, Error>({
    queryKey: [TASKS_QUERY_KEY_PREFIX, 'scheduledJobs'],
    queryFn: () => apiClient._fetch(`${tasksBasePath}${schedulePath}/jobs`),
  });
}

export function useJobStatus(jobId: string | null | undefined) {
  return useQuery<JobStatusResponse, Error>({
    queryKey: [TASKS_QUERY_KEY_PREFIX, 'jobStatus', jobId],
    queryFn: () => {
      if (!jobId) return Promise.reject(new Error("Job ID is required"));
      return apiClient._fetch(`${tasksBasePath}${schedulePath}/jobs/${jobId}/status`);
    },
    enabled: !!jobId,
    // Consider refetchInterval if status needs polling
  });
}

export function useAvailableFunctions() {
  return useQuery<FunctionInfo[], Error>({
    queryKey: [TASKS_QUERY_KEY_PREFIX, 'availableFunctions'],
    queryFn: async () => {
        try {
            const response = await apiClient._fetch(`${tasksBasePath}${functionsPath}/`);
            if (!Array.isArray(response)) {
                console.error("Unexpected response format from functions API", response);
                return [];
            }
            return response;
        } catch (error) {
            console.error("Error fetching available functions:", error);
            throw error;
        }
    },
  });
}

export function useFunctionInfo(functionPath: string | null | undefined) {
  return useQuery<FunctionInfoResponse, Error>({
    queryKey: [TASKS_QUERY_KEY_PREFIX, 'functionInfo', functionPath],
    queryFn: () => {
      if (!functionPath) return Promise.reject(new Error("Function path is required"));
      return apiClient._fetch(`${tasksBasePath}${functionsPath}/${functionPath}`);
    },
    enabled: !!functionPath,
  });
}

// --- Mutation Hooks ---
export function useScheduleFunctionMutation() {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  return useMutation<ScheduleResponse, Error, { functionPath: string; config: TaskConfig }>({
    mutationFn: ({ functionPath, config }) => 
        apiClient._fetch(`${tasksBasePath}${schedulePath}/functions/schedule`, { 
            method: 'POST',
            body: JSON.stringify({
                function_path: functionPath,
                config,
            } as CreateTaskRequest),
        }),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: [TASKS_QUERY_KEY_PREFIX, 'scheduledJobs'] });
      toast({ title: "Success", description: data.message || "Function scheduled." });
    },
    onError: (error) => {
      toast({ variant: "destructive", title: "Error", description: error.message || "Failed to schedule function." });
    },
  });
}

export function useRunFunctionMutation() {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  return useMutation<QueuedTaskResponse, Error, { functionPath: string; parameters?: Record<string, any> }>({
    mutationFn: ({ functionPath, parameters }) => 
        apiClient._fetch(`${tasksBasePath}${schedulePath}/functions/run`, { 
            method: 'POST',
            body: JSON.stringify({
                function_path: functionPath,
                parameters: parameters,
            } as RunFunctionRequest),
        }),
    onSuccess: (data) => {
      // May need to invalidate specific job status if ID is known, or scheduled jobs if it appears there.
      queryClient.invalidateQueries({ queryKey: [TASKS_QUERY_KEY_PREFIX, 'scheduledJobs'] });
      toast({ title: "Success", description: data.message || "Function run queued." });
    },
    onError: (error) => {
      toast({ variant: "destructive", title: "Error", description: error.message || "Failed to run function." });
    },
  });
}

export function usePauseScheduledJobMutation() {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  return useMutation<SimpleJobResponse, Error, string>({
    mutationFn: (jobId: string) => apiClient._fetch(`${tasksBasePath}${schedulePath}/jobs/${jobId}/pause`, { method: 'PUT' }),
    onSuccess: (data, jobId) => {
      queryClient.invalidateQueries({ queryKey: [TASKS_QUERY_KEY_PREFIX, 'scheduledJobs'] });
      queryClient.invalidateQueries({ queryKey: [TASKS_QUERY_KEY_PREFIX, 'jobStatus', jobId] });
      toast({ title: "Success", description: data.message || "Job paused." });
    },
    onError: (error) => {
      toast({ variant: "destructive", title: "Error", description: error.message || "Failed to pause job." });
    },
  });
}

export function useResumeScheduledJobMutation() {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  return useMutation<SimpleJobResponse, Error, string>({
    mutationFn: (jobId: string) => apiClient._fetch(`${tasksBasePath}${schedulePath}/jobs/${jobId}/resume`, { method: 'PUT' }),
    onSuccess: (data, jobId) => {
      queryClient.invalidateQueries({ queryKey: [TASKS_QUERY_KEY_PREFIX, 'scheduledJobs'] });
      queryClient.invalidateQueries({ queryKey: [TASKS_QUERY_KEY_PREFIX, 'jobStatus', jobId] });
      toast({ title: "Success", description: data.message || "Job resumed." });
    },
    onError: (error) => {
      toast({ variant: "destructive", title: "Error", description: error.message || "Failed to resume job." });
    },
  });
}

export function useDeleteScheduledJobMutation() {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  return useMutation<SimpleJobResponse, Error, string>({
    mutationFn: (jobId: string) => apiClient._fetch(`${tasksBasePath}${schedulePath}/jobs/${jobId}`, { method: 'DELETE' }),
    onSuccess: (data, jobId) => {
      queryClient.invalidateQueries({ queryKey: [TASKS_QUERY_KEY_PREFIX, 'scheduledJobs'] });
      queryClient.removeQueries({ queryKey: [TASKS_QUERY_KEY_PREFIX, 'jobStatus', jobId] });
      toast({ title: "Success", description: data.message || "Job deleted." });
    },
    onError: (error) => {
      toast({ variant: "destructive", title: "Error", description: error.message || "Failed to delete job." });
    },
  });
}

// --- Streaming Function ---
export function subscribeToJobLogs(
  instance: APIClient, // Explicitly pass apiClient instance
  jobId: string,
  onMessage: (message: string) => void,
  onError?: (error: any) => void,
  onComplete?: () => void
) {
  const path = `${tasksBasePath}${schedulePath}/jobs/${jobId}/logs?min_level=INFO`;
  return instance.createFetchStream(path, onMessage, onError, onComplete);
} 