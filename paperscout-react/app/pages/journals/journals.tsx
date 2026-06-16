"use client";

import { DataTable } from "~/components/data-table";
import { columns, type Journal } from "./columns";

interface JournalsPageProps {
  initialData: Journal[];
  initialError: string | null;
  rowSelection: any;
  onRowSelectionChange: (selection: any) => void;
}

export default function JournalsPage({ 
  initialData, 
  initialError, 
  rowSelection, 
  onRowSelectionChange 
}: JournalsPageProps) {
  // Die Komponente ist jetzt "stateless" bezüglich des Ladens – sie zeigt nur an.
  return (
    <div className="flex h-full w-full flex-col md:p-1">
      {initialError && <div className="text-destructive p-2">{initialError}</div>}
      <DataTable 
        columns={columns} 
        data={initialData} 
        rowSelection={rowSelection} 
        onRowSelectionChange={onRowSelectionChange} 
      />
    </div>
  );
}
