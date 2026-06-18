// app/routes/_index.tsx
import { endOfMonth, format, startOfMonth } from "date-fns";
import { useEffect, useMemo, useState } from "react";
import { type DateRange } from "react-day-picker";
import { useLoaderData, useNavigate } from "react-router";
import { InputAccordion } from "~/components/input-accordion";
import { type Journal } from "~/pages/journals/columns";
import JournalsPage from "~/pages/journals/journals";
import RangePage from "~/pages/range/range";
import SearchPage from "~/pages/search/search";

export async function clientLoader() {
  const journals = fetch("http://localhost:8000/api/journals")
    .then((response) => {
      if (!response.ok) throw new Error("Fehler beim Laden der Journals");
      return response.json();
    })
    .then((data) => {
      return (data.results as Journal[]) || [];
    });

  return { journals };
}

export default function Home() {
  // Auswahlzustand für die Journals
  const { journals } = useLoaderData();

  const [rowSelection, setRowSelection] = useState(() => {
    const saved = sessionStorage.getItem("ps_row_selection");
    return saved ? JSON.parse(saved) : {};
  });

  // Zustand für den Date Picker
  const [date, setDate] = useState<DateRange | undefined>(() => {
    const saved = sessionStorage.getItem("ps_date_range");
    if (saved) {
      const parsed = JSON.parse(saved);
      return {
        from: parsed.from ? new Date(parsed.from) : undefined,
        to: parsed.to ? new Date(parsed.to) : undefined,
      };
    }
    const now = new Date();
    return { from: startOfMonth(now), to: endOfMonth(now) };
  });

  // Zustand für den Suchbegriff
  const [searchTerm, setSearchTerm] = useState(() => {
    return sessionStorage.getItem("ps_search_term") || "";
  });

  // Zustand für die Ergebnisse
  const navigate = useNavigate(); // Hook für die Navigation

  // Effekte zum Synchronisieren mit dem SessionStorage
  useEffect(() => {
    sessionStorage.setItem("ps_row_selection", JSON.stringify(rowSelection));
  }, [rowSelection]);

  useEffect(() => {
    sessionStorage.setItem("ps_date_range", JSON.stringify(date));
  }, [date]);

  useEffect(() => {
    sessionStorage.setItem("ps_search_term", searchTerm);
  }, [searchTerm]);

  const handleSearch = async () => {
    if (!date?.from || !date?.to) return;

    try {
      // Extrahiere die OpenAlex IDs der ausgewählten Journals aus dem RowSelection State

      // Filtert nur die Keys heraus, deren Wert im rowSelection-Objekt explizit 'true' ist
      const selectedJournalIds = Object.entries(rowSelection)
        .filter(([_, selected]) => selected === true)
        .map(([id]) => id);

      const params = new URLSearchParams();
      // Mehrere IDs müssen als separate Query-Parameter mit gleichem Namen angehängt werden
      selectedJournalIds.forEach((id) => params.append("journal_ids", id));

      // Stellt sicher, dass keywords immer übergeben wird, auch als leerer String ""
      params.append("keywords", searchTerm.trim() || "");
      params.append("from_date", format(date.from, "yyyy-MM-dd"));
      params.append("to_date", format(date.to, "yyyy-MM-dd"));

      // Speichere die Suchparameter im Session Storage
      sessionStorage.setItem("lastSearchParams", params.toString());

      navigate(`/results?${params.toString()}`);
    } catch (err) {
      console.error("Fehler bei der Artikelsuche:", err);
    }
  };

  // Memoize die Inhalte der Akkordeon-Elemente, um unnötiges Remounting zu verhindern
  const journalsContent = useMemo(
    () => (
      <JournalsPage
        initialData={journals}
        rowSelection={rowSelection}
        onRowSelectionChange={setRowSelection}
      />
    ),
    [rowSelection, setRowSelection],
  );

  const rangeContent = useMemo(
    () => <RangePage date={date} onDateChange={setDate} />,
    [date, setDate],
  );

  const searchContent = useMemo(
    () => (
      <SearchPage searchTerm={searchTerm} onSearchTermChange={setSearchTerm} />
    ),
    [searchTerm, setSearchTerm],
  );

  const accordionItems = useMemo(
    () => [
      {
        value: "journals",
        trigger: "Search for Journals",
        content: journalsContent,
      },
      {
        value: "range",
        trigger: "Enter a Search Time Range",
        content: rangeContent,
      },
      {
        value: "search",
        trigger: "Enter a Search Term",
        content: searchContent,
      },
    ],
    [journalsContent, rangeContent, searchContent],
  );

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
