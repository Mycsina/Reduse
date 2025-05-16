import { useMutation } from '@tanstack/react-query';
import apiClient from '@/lib/api-client';
import { useToast } from '@/hooks/use-toast';

const basePath = '/bug-reports';
const BUG_REPORTS_QUERY_KEY_PREFIX = 'bugReports';

/**
 * Type of bug report.
 */
export enum BugReportType {
  INCORRECT_DATA = "incorrect_data",
  MISSING_DATA = "missing_data",
  WRONG_ANALYSIS = "wrong_analysis",
  DUPLICATE_LISTING = "duplicate_listing",
  OTHER = "other",
}

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

export interface BugReportResponse extends BugReportCreate {
    id: string;
    created_at: string;
    status?: string;
}

export function useCreateBugReportMutation() {
  const { toast } = useToast();

  return useMutation<BugReportResponse, Error, BugReportCreate>({
    mutationFn: (report: BugReportCreate) => 
        apiClient._fetch(`${basePath}`, {
            method: 'POST',
            body: JSON.stringify(report),
        }),
    onSuccess: (data) => {
      toast({ title: "Bug Report Submitted", description: "Thank you for your feedback!" });
    },
    onError: (error) => {
      toast({ variant: "destructive", title: "Submission Failed", description: error.message || "Could not submit bug report." });
    },
  });
} 