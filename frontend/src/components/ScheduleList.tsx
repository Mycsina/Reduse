import { Button } from '@/components/ui/button'
import { apiClient } from '@/lib/api-client'

export default async function ScheduleList() {
  const jobs = await apiClient.getScheduledJobs()

  return (
    <ul className="space-y-4">
      {jobs.map((job: any) => (
        <li key={job.id} className="border p-4 rounded-lg">
          <p><strong>ID:</strong> {job.id}</p>
          <p><strong>Function:</strong> {job.func}</p>
          <p><strong>Next Run:</strong> {new Date(job.next_run_time).toLocaleString()}</p>
          <p><strong>Trigger:</strong> {job.trigger}</p>
          <form action={`/api/schedule/delete/${job.id}`} method="POST" className="mt-2">
            <Button type="submit" variant="destructive">Delete</Button>
          </form>
        </li>
      ))}
    </ul>
  )
}

