"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "~/components/ui/card";
import { DataTable } from "~/components/ui/data-table";
import { columns, type Journal } from "./columns";

export default function SearchPage() {
  // Ein Standard-Suchbegriff, da die API 'query' zwingend erfordert
  const [journals, setJournals] = useState<Journal[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchJournals = async (searchQuery: string) => {
    if (!searchQuery.trim()) return;

    setLoading(true);
    setError(null);
    try {
      const response = await fetch(
        `http://localhost:8000/api/search/journals?query=${encodeURIComponent(searchQuery)}`,
      );
      if (!response.ok) {
        throw new Error("Fehler beim Laden der Journals.");
      }
      const data = await response.json();
      console.log(data);
      setJournals(data.results || []);
    } catch (err: any) {
      setError(err.message);
      setJournals([]);
    } finally {
      setLoading(false);
    }
  };

  // Der useEffect Hook führt den Fetch automatisch beim ersten Laden der Seite aus
  useEffect(() => {
    fetchJournals("science");
  }, []); // Das leere Array bedeutet: Nur ein einziges Mal beim Initial-Render ausführen

  return (
    <div className="w-full md:p-1">
      <Card>
        <CardHeader>
          <CardTitle>Welcome to React Journals v7</CardTitle>
        </CardHeader>
        <CardContent>
          <DataTable columns={columns} data={journals} />
        </CardContent>
      </Card>
    </div>
  );
}
