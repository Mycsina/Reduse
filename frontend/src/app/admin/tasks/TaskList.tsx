"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { useRouter } from "next/navigation";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";

import {
  usePauseScheduledJobMutation,
  useResumeScheduledJobMutation,
  useDeleteScheduledJobMutation,
  useScheduledJobs,
} from "@/lib/api/admin/tasks";

interface ScheduledJob {
  id: string;
  func: string;
  next_run_time: string | null | undefined;
  trigger: string;
  max_instances: number;
}

interface TaskStatus {
  status: string;
  error?: string;
  result?: any;
}

export default function TaskList() {
  const [taskHistory, setTaskHistory] = useState<Record<string, TaskStatus>>(
    {},
  );
  const [selectedTab, setSelectedTab] = useState("scheduled");
  const router = useRouter();

  const {
    data: scheduledJobsData,
    isLoading: isLoadingJobs,
    isError: isErrorJobs,
    error: jobsError,
  } = useScheduledJobs();
  const scheduledJobs: ScheduledJob[] = scheduledJobsData || []; // Assume scheduledJobsData is the array and type it

  const pauseMutation = usePauseScheduledJobMutation();
  const resumeMutation = useResumeScheduledJobMutation();
  const deleteMutation = useDeleteScheduledJobMutation();

  const handlePause = async (jobId: string) => {
    await pauseMutation.mutateAsync(jobId);
  };

  const handleResume = async (jobId: string) => {
    await resumeMutation.mutateAsync(jobId);
  };

  const handleDelete = async (jobId: string) => {
    await deleteMutation.mutateAsync(jobId);
  };

  const fetchTaskStatus = async (jobId: string) => {
    try {
      console.log("Fetch status for", jobId);
    } catch (error) {
      console.error(`Failed to fetch status for job ${jobId}:`, error);
    }
  };

  if (isErrorJobs) {
    return <p>Error loading scheduled jobs: {jobsError?.message}</p>;
  }

  return (
    <Tabs value={selectedTab} onValueChange={setSelectedTab}>
      <TabsList>
        <TabsTrigger value="scheduled">Scheduled Jobs</TabsTrigger>
        <TabsTrigger value="history">Task History</TabsTrigger>
      </TabsList>

      <TabsContent value="scheduled">
        {isLoadingJobs && <p>Loading scheduled jobs...</p>}
        {!isLoadingJobs && (
          <ScrollArea className="h-[400px]">
            <div className="space-y-4">
              {scheduledJobs.map((job) => (
                <Card key={job.id} className="p-4">
                  <div className="flex items-start justify-between">
                    <div>
                      <p className="font-semibold">{job.func}</p>
                      <p className="text-muted-foreground text-sm">
                        Next Run:{" "}
                        {job.next_run_time
                          ? new Date(job.next_run_time).toLocaleString()
                          : "N/A"}
                      </p>
                      <p className="text-muted-foreground text-sm">
                        Trigger: {job.trigger}
                      </p>
                      <p className="text-muted-foreground text-sm">
                        Max Instances: {job.max_instances}
                      </p>
                    </div>
                    <div className="space-x-2">
                      <Button
                        onClick={() => handlePause(job.id)}
                        variant="secondary"
                        disabled={pauseMutation.isPending}
                        size="sm"
                      >
                        Pause
                      </Button>
                      <Button
                        onClick={() => handleResume(job.id)}
                        variant="secondary"
                        disabled={resumeMutation.isPending}
                        size="sm"
                      >
                        Resume
                      </Button>
                      <Button
                        onClick={() => handleDelete(job.id)}
                        variant="destructive"
                        disabled={deleteMutation.isPending}
                        size="sm"
                      >
                        Delete
                      </Button>
                    </div>
                  </div>
                </Card>
              ))}
              {scheduledJobs.length === 0 && !isLoadingJobs && (
                <p className="text-muted-foreground text-center">
                  No scheduled jobs found
                </p>
              )}
            </div>
          </ScrollArea>
        )}
      </TabsContent>

      <TabsContent value="history">
        <ScrollArea className="h-[400px]">
          <div className="space-y-4">
            {Object.entries(taskHistory).map(([jobId, status]) => (
              <Card key={jobId} className="p-4">
                <div>
                  <p className="font-semibold">Job ID: {jobId}</p>
                  <p className="text-muted-foreground text-sm">
                    Status: {status.status}
                  </p>
                  {status.error && (
                    <p className="text-sm text-red-500">
                      Error: {status.error}
                    </p>
                  )}
                  {status.result && (
                    <pre className="bg-muted mt-2 overflow-x-auto rounded p-2 text-sm">
                      {JSON.stringify(status.result, null, 2)}
                    </pre>
                  )}
                </div>
              </Card>
            ))}
            {Object.keys(taskHistory).length === 0 && (
              <p className="text-muted-foreground text-center">
                No task history found (Note: History fetching is not actively
                implemented in this view)
              </p>
            )}
          </div>
        </ScrollArea>
      </TabsContent>
    </Tabs>
  );
}
