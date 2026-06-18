"use client";

import { DataTable } from "~/components/data-table";
import { columns, type Journal } from "./columns";

interface JournalsPageProps {
  initialData: Journal[];
  rowSelection: any;
  onRowSelectionChange: (selection: any) => void;
}

export default function JournalsPage({
  initialData,
  rowSelection,
  onRowSelectionChange,
}: JournalsPageProps) {
  return (
    <div className="flex h-full w-full flex-col md:p-1">
      <DataTable
        columns={columns}
        initialData={initialData}
        rowSelection={rowSelection}
        onRowSelectionChange={onRowSelectionChange}
      />
    </div>
  );
}
