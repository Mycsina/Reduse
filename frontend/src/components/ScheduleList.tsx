"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { apiClient } from "@/lib/api-client";
import { toast } from "@/hooks/use-toast";
import { useRouter } from "next/navigation";

export default function ScheduleList() {
  const [jobs, setJobs] = useState<
    {
      id: string;
      next_run_time: string;
      func: string;
      trigger: string;
      max_instances: number;
    }[]
  >([]);
  const [isLoading, setIsLoading] = useState(false);
  const router = useRouter();

  const fetchJobs = async () => {
    try {
      const jobs = await apiClient.getScheduledJobs();
      setJobs(jobs);
    } catch (error) {
      toast({
        title: "Failed to fetch jobs",
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
      await fetchJobs();
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
      await fetchJobs();
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
      await fetchJobs();
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

  useEffect(() => {
    fetchJobs();
  }, []);

  return (
    <ul className="space-y-4">
      {jobs.map((job) => (
        <li key={job.id} className="border p-4 rounded-lg">
          <p>
            <strong>ID:</strong> {job.id}
          </p>
          <p>
            <strong>Function:</strong> {job.func}
          </p>
          <p>
            <strong>Next Run:</strong>{" "}
            {new Date(job.next_run_time).toLocaleString()}
          </p>
          <p>
            <strong>Trigger:</strong> {job.trigger}
          </p>
          <div className="mt-2 space-x-2">
            <Button
              onClick={() => handlePause(job.id)}
              variant="secondary"
              disabled={isLoading}
            >
              Pause
            </Button>
            <Button
              onClick={() => handleResume(job.id)}
              variant="secondary"
              disabled={isLoading}
            >
              Resume
            </Button>
            <Button
              onClick={() => handleDelete(job.id)}
              variant="destructive"
              disabled={isLoading}
            >
              Delete
            </Button>
          </div>
        </li>
      ))}
    </ul>
  );
}
