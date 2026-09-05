"use client";

import type { OnChangeFn, RowSelectionState } from "@tanstack/react-table";
import { DataTable } from "~/components/data-table";
import { columns, type Journal } from "./columns";

interface JournalsPageProps {
  data: Journal[];
  isLoading?: boolean;
  rowSelection: RowSelectionState;
  onRowSelectionChange: OnChangeFn<RowSelectionState>;
}

export default function JournalsPage({
  data,
  isLoading,
  rowSelection,
  onRowSelectionChange,
}: JournalsPageProps) {
  return (
    <div className="flex h-full w-full flex-col md:p-1">
      <DataTable
        columns={columns}
        data={data}
        isLoading={isLoading}
        rowSelection={rowSelection}
        onRowSelectionChange={onRowSelectionChange}
      />
    </div>
  );
}
