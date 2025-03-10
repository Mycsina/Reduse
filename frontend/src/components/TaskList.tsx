"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { apiClient } from "@/lib/api-client";
import { toast } from "@/hooks/use-toast";
import { useRouter } from "next/navigation";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";

interface ScheduledJob {
  id: string;
  next_run_time: string;
  func: string;
  trigger: string;
  max_instances: number;
}

interface TaskStatus {
  status: string;
  result?: any;
  error?: string;
}

export default function TaskList() {
  const [scheduledJobs, setScheduledJobs] = useState<ScheduledJob[]>([]);
  const [taskHistory, setTaskHistory] = useState<Record<string, TaskStatus>>(
    {}
  );
  const [isLoading, setIsLoading] = useState(false);
  const [selectedTab, setSelectedTab] = useState("scheduled");
  const router = useRouter();

  const fetchScheduledJobs = async () => {
    try {
      const response = await apiClient.getScheduledJobs();
      setScheduledJobs(response.jobs);
    } catch (error) {
      toast({
        title: "Failed to fetch scheduled jobs",
        description:
          error instanceof Error ? error.message : "Unknown error occurred",
        variant: "destructive",
      });
    }
  };

  const handlePause = async (jobId: string) => {
    try {
      setIsLoading(true);
      await apiClient.pauseScheduledJob(jobId);
      toast({ title: "Job paused successfully" });
      await fetchScheduledJobs();
    } catch (error) {
      toast({
        title: "Failed to pause job",
        description:
          error instanceof Error ? error.message : "Unknown error occurred",
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleResume = async (jobId: string) => {
    try {
      setIsLoading(true);
      await apiClient.resumeScheduledJob(jobId);
      toast({ title: "Job resumed successfully" });
      await fetchScheduledJobs();
    } catch (error) {
      toast({
        title: "Failed to resume job",
        description:
          error instanceof Error ? error.message : "Unknown error occurred",
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleDelete = async (jobId: string) => {
    try {
      setIsLoading(true);
      await apiClient.deleteScheduledJob(jobId);
      toast({ title: "Job deleted successfully" });
      await fetchScheduledJobs();
    } catch (error) {
      toast({
        title: "Failed to delete job",
        description:
          error instanceof Error ? error.message : "Unknown error occurred",
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  };

  const fetchTaskStatus = async (jobId: string) => {
    try {
      const status = await apiClient.getJobStatus(jobId);
      setTaskHistory((prev) => ({
        ...prev,
        [jobId]: status,
      }));
    } catch (error) {
      console.error(`Failed to fetch status for job ${jobId}:`, error);
    }
  };

  useEffect(() => {
    fetchScheduledJobs();
  }, []);

  return (
    <Tabs value={selectedTab} onValueChange={setSelectedTab}>
      <TabsList>
        <TabsTrigger value="scheduled">Scheduled Jobs</TabsTrigger>
        <TabsTrigger value="history">Task History</TabsTrigger>
      </TabsList>

      <TabsContent value="scheduled">
        <ScrollArea className="h-[400px]">
          <div className="space-y-4">
            {scheduledJobs.map((job) => (
              <Card key={job.id} className="p-4">
                <div className="flex justify-between items-start">
                  <div>
                    <p className="font-semibold">{job.func}</p>
                    <p className="text-sm text-muted-foreground">
                      Next Run: {new Date(job.next_run_time).toLocaleString()}
                    </p>
                    <p className="text-sm text-muted-foreground">
                      Trigger: {job.trigger}
                    </p>
                    <p className="text-sm text-muted-foreground">
                      Max Instances: {job.max_instances}
                    </p>
                  </div>
                  <div className="space-x-2">
                    <Button
                      onClick={() => handlePause(job.id)}
                      variant="secondary"
                      disabled={isLoading}
                      size="sm"
                    >
                      Pause
                    </Button>
                    <Button
                      onClick={() => handleResume(job.id)}
                      variant="secondary"
                      disabled={isLoading}
                      size="sm"
                    >
                      Resume
                    </Button>
                    <Button
                      onClick={() => handleDelete(job.id)}
                      variant="destructive"
                      disabled={isLoading}
                      size="sm"
                    >
                      Delete
                    </Button>
                  </div>
                </div>
              </Card>
            ))}
            {scheduledJobs.length === 0 && (
              <p className="text-center text-muted-foreground">
                No scheduled jobs found
              </p>
            )}
          </div>
        </ScrollArea>
      </TabsContent>

      <TabsContent value="history">
        <ScrollArea className="h-[400px]">
          <div className="space-y-4">
            {Object.entries(taskHistory).map(([jobId, status]) => (
              <Card key={jobId} className="p-4">
                <div>
                  <p className="font-semibold">Job ID: {jobId}</p>
                  <p className="text-sm text-muted-foreground">
                    Status: {status.status}
                  </p>
                  {status.error && (
                    <p className="text-sm text-red-500">
                      Error: {status.error}
                    </p>
                  )}
                  {status.result && (
                    <pre className="text-sm bg-muted p-2 rounded mt-2 overflow-x-auto">
                      {JSON.stringify(status.result, null, 2)}
                    </pre>
                  )}
                </div>
              </Card>
            ))}
            {Object.keys(taskHistory).length === 0 && (
              <p className="text-center text-muted-foreground">
                No task history found
              </p>
            )}
          </div>
        </ScrollArea>
      </TabsContent>
    </Tabs>
  );
}
