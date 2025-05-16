"use client";

import { Button } from "@/components/ui/button";
import {
  useScheduledJobs,
  usePauseScheduledJobMutation,
  useResumeScheduledJobMutation,
  useDeleteScheduledJobMutation,
} from "@/lib/api/admin/tasks";

interface ScheduledJob {
  id: string;
  next_run_time: string;
  func: string;
  trigger: string;
  max_instances: number;
}

export default function ScheduleList() {
  const {
    data: jobsData,
    isLoading: isLoadingJobs,
    error: jobsError,
  } = useScheduledJobs();
  const { mutate: pauseJob, isPending: isPausing } =
    usePauseScheduledJobMutation();
  const { mutate: resumeJob, isPending: isResuming } =
    useResumeScheduledJobMutation();
  const { mutate: deleteJob, isPending: isDeleting } =
    useDeleteScheduledJobMutation();

  const handlePause = (jobId: string) => {
    pauseJob(jobId);
  };

  const handleResume = (jobId: string) => {
    resumeJob(jobId);
  };

  const handleDelete = (jobId: string) => {
    deleteJob(jobId);
  };

  if (isLoadingJobs) {
    return <div>Loading scheduled jobs...</div>;
  }

  if (jobsError) {
    return <div>Error loading jobs: {jobsError.message}</div>;
  }

  const jobs: ScheduledJob[] = jobsData || [];

  return (
    <ul className="space-y-4">
      {jobs.map((job: ScheduledJob) => (
        <li key={job.id} className="rounded-lg border p-4">
          <p>
            <strong>ID:</strong> {job.id}
          </p>
          <p>
            <strong>Function:</strong> {job.func}
          </p>
          <p>
            <strong>Next Run:</strong>{" "}
            {job.next_run_time
              ? new Date(job.next_run_time).toLocaleString()
              : "N/A"}
          </p>
          <p>
            <strong>Trigger:</strong> {job.trigger}
          </p>
          <div className="mt-2 space-x-2">
            <Button
              onClick={() => handlePause(job.id)}
              variant="secondary"
              disabled={isPausing || isResuming || isDeleting}
            >
              Pause
            </Button>
            <Button
              onClick={() => handleResume(job.id)}
              variant="secondary"
              disabled={isPausing || isResuming || isDeleting}
            >
              Resume
            </Button>
            <Button
              onClick={() => handleDelete(job.id)}
              variant="destructive"
              disabled={isPausing || isResuming || isDeleting}
            >
              Delete
            </Button>
          </div>
        </li>
      ))}
      {jobs.length === 0 && !isLoadingJobs && <p>No scheduled jobs found.</p>}
    </ul>
  );
}
