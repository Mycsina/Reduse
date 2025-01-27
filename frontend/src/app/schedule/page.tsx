import { Suspense } from 'react'
import { Skeleton } from '@/components/ui/skeleton'
import ScheduleList from '@/components/ScheduleList'
import ScheduleForm from '@/components/ScheduleForm'

export default function SchedulePage() {
  return (
    <div>
      <h1 className="text-3xl font-bold mb-6">Schedule</h1>
      <div className="mb-8">
        <h2 className="text-2xl font-semibold mb-4">Create New Schedule</h2>
        <ScheduleForm />
      </div>
      <div>
        <h2 className="text-2xl font-semibold mb-4">Scheduled Jobs</h2>
        <Suspense fallback={<Skeleton className="h-[200px]" />}>
          <ScheduleList />
        </Suspense>
      </div>
    </div>
  )
}

