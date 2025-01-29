"use client";

import { Suspense } from "react";
import { Skeleton } from "@/components/ui/skeleton";
import TaskList from "@/components/TaskList";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import RunFunction from "@/components/RunFunction";
import ScheduleForm from "@/components/ScheduleForm";
import FunctionScheduler from "@/components/FunctionScheduler";

export default function TasksPage() {
  return (
    <div>
      <h1 className="text-3xl font-bold mb-6">Tasks</h1>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Left Column: Run Functions */}
        <Card className="p-6">
          <h2 className="text-2xl font-semibold mb-4">Run Function</h2>
          <RunFunction />
        </Card>

        {/* Right Column: Schedule Tasks */}
        <Card className="p-6">
          <h2 className="text-2xl font-semibold mb-4">Schedule Task</h2>
          <Tabs defaultValue="predefined">
            <TabsList>
              <TabsTrigger value="predefined">Predefined Jobs</TabsTrigger>
              <TabsTrigger value="function">Custom Functions</TabsTrigger>
            </TabsList>
            <TabsContent value="predefined">
              <ScheduleForm />
            </TabsContent>
            <TabsContent value="function">
              <FunctionScheduler />
            </TabsContent>
          </Tabs>
        </Card>
      </div>

      <Separator className="my-8" />

      {/* Task List */}
      <div>
        <h2 className="text-2xl font-semibold mb-4">Task History</h2>
        <Suspense fallback={<Skeleton className="h-[200px]" />}>
          <TaskList />
        </Suspense>
      </div>
    </div>
  );
}
