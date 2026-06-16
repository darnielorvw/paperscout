// app/routes/_index.tsx
import { endOfMonth, format, startOfMonth } from "date-fns";
import { useMemo, useState } from "react";
import { type DateRange } from "react-day-picker";
import { useLoaderData } from "react-router";
import { InputAccordion } from "~/components/input-accordion";
import JournalsPage from "~/pages/journals/journals";
import RangePage from "~/pages/range/range";
import SearchPage from "~/pages/search/search";

// Der Loader läuft einmalig beim Aufrufen der Route
export async function clientLoader() {
  try {
    const response = await fetch("http://localhost:8000/api/journals");
    if (!response.ok) throw new Error("Fehler beim Laden");
    const data = await response.json();
    return { journals: data.results || [], error: null };
  } catch (err: any) {
    return { journals: [], error: err.message };
  }
}

export default function Home() {
  // Wir holen die Daten hier auf Route-Ebene ab
  const { journals, error } = useLoaderData<typeof clientLoader>();
  // Auswahlzustand für die Journals
  const [rowSelection, setRowSelection] = useState({});
  // Zustand für den Date Picker
  const [date, setDate] = useState<DateRange | undefined>(() => {
    const now = new Date();
    return { from: startOfMonth(now), to: endOfMonth(now) };
  });
  // Zustand für den Suchbegriff
  const [searchTerm, setSearchTerm] = useState("");
  // Zustand für die Ergebnisse
  const [articles, setArticles] = useState([]);

  const handleSearch = async () => {
    if (!date?.from || !date?.to) return;

    try {
      // Extrahiere die OpenAlex IDs der ausgewählten Journals aus dem RowSelection State
      const selectedJournalIds = Object.keys(rowSelection).map(
        (index) => journals[parseInt(index)].id
      );

      const params = new URLSearchParams();
      // Mehrere IDs müssen als separate Query-Parameter mit gleichem Namen angehängt werden
      selectedJournalIds.forEach((id) => params.append("journal_ids", id));
      params.append("keywords", searchTerm);
      params.append("from_date", format(date.from, "yyyy-MM-dd"));
      params.append("to_date", format(date.to, "yyyy-MM-dd"));

      const response = await fetch(`http://localhost:8000/api/articles?${params.toString()}`);
      
      if (!response.ok) throw new Error("Suche fehlgeschlagen");

      const data = await response.json();
      setArticles(data.results);
      console.log("Gefundene Artikel:", data.results);
    } catch (err) {
      console.error("Fehler bei der Artikelsuche:", err);
    }
  };

  // Memoize die Inhalte der Akkordeon-Elemente, um unnötiges Remounting zu verhindern
  const journalsContent = useMemo(() => (
    <JournalsPage
      initialData={journals}
      initialError={error}
      rowSelection={rowSelection}
      onRowSelectionChange={setRowSelection}
    />
  ), [journals, error, rowSelection, setRowSelection]);

  const rangeContent = useMemo(() => (
    <RangePage date={date} onDateChange={setDate} />
  ), [date, setDate]);

  const searchContent = useMemo(() => (
    <SearchPage
      searchTerm={searchTerm}
      onSearchTermChange={setSearchTerm}
    />
  ), [searchTerm, setSearchTerm]);

  const accordionItems = useMemo(() => [
    {
      value: "journals",
      trigger: "Search for Journals",
      content: journalsContent
    },
    {
      value: "range",
      trigger: "Enter a Search Time Range",
      content: rangeContent
    },
    {
      value: "search",
      trigger: "Enter a Search Term",
      content: searchContent
    }
  ], [journalsContent, rangeContent, searchContent]);

  return (
    <div className="h-full w-full">
      <InputAccordion 
        title="PaperScout Dashboard" 
        description="Wähle eine Aktion aus dem Menü." 
        items={accordionItems} 
        onFinish={handleSearch}
      />
    </div>
  );
}
