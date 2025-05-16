"use client";

import React from "react";
import { Suspense } from "react";
import { Skeleton } from "@/components/ui/skeleton";
import TaskList from "@/app/admin/tasks/TaskList";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import RunFunction from "@/app/admin/tasks/RunFunction";
import ScheduleForm from "@/app/admin/tasks/ScheduleForm";
import FunctionScheduler from "@/app/admin/tasks/FunctionScheduler";
import { Title } from "@/components/ui/text/Title";

export default function TasksPage() {
  return (
    <div className="space-y-6">
      <Title>Task Management</Title>

      <div className="grid grid-cols-1 gap-8 lg:grid-cols-2">
        {/* Left Column: Run Functions */}
        <Card className="p-6">
          <h2 className="mb-4 text-2xl font-semibold">Run Function</h2>
          <RunFunction />
        </Card>

        {/* Right Column: Schedule Tasks */}
        <Card className="p-6">
          <h2 className="mb-4 text-2xl font-semibold">Schedule Task</h2>
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
        <h2 className="mb-4 text-2xl font-semibold">Task History</h2>
        <Suspense fallback={<Skeleton className="h-[200px]" />}>
          <TaskList />
        </Suspense>
      </div>
    </div>
  );
}
