"use client";

import { DataTable } from "~/components/data-table";
import { columns, type Journal } from "./columns";

interface JournalsPageProps {
  initialData: Journal[];
  initialError: string | null;
  rowSelection: any;
  onRowSelectionChange: (selection: any) => void;
  isLoading: boolean;
}

export default function JournalsPage({
  initialData,
  initialError,
  rowSelection,
  onRowSelectionChange,
  isLoading,
}: JournalsPageProps) {
  return (
    <div className="flex h-full w-full flex-col md:p-1">
      {initialError && (
        <div className="text-destructive p-2">{initialError}</div>
      )}

      <DataTable
        columns={columns}
        data={initialData}
        rowSelection={rowSelection}
        onRowSelectionChange={onRowSelectionChange}
        isLoading={isLoading}
      />
    </div>
  );
}
