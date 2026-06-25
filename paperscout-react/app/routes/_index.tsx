// app/routes/_index.tsx
import { useEffect, useMemo } from "react";
import { useLoaderData, useLocation, useNavigate } from "react-router";
import { InputAccordion } from "~/components/input-accordion";
import { useSearch } from "~/context/search-context";
import { apiFetch } from "~/lib/api";
import { buildResultsUrl } from "~/lib/search-utils";
import { type Journal } from "~/pages/journals/columns";
import JournalsPage from "~/pages/journals/journals";
import RangePage from "~/pages/range/range";
import SearchPage from "~/pages/search/search";

export async function clientLoader() {
  const journals = apiFetch("http://localhost:8000/api/journals")
    .then((data) => {
      return (data.results as Journal[]) || [];
    });

  return { journals };
}

export default function Home() {
  // Auswahlzustand für die Journals
  const { journals } = useLoaderData<typeof clientLoader>();
  const {
    rowSelection,
    setRowSelection,
    date,
    setDate,
    searchTerm,
    setSearchTerm,
  } = useSearch();

  // Zustand für die Ergebnisse
  const navigate = useNavigate(); // Hook für die Navigation
  const location = useLocation();

  // Effekt, um sicherzustellen, dass die Startseite immer auf #journals zeigt.
  useEffect(() => {
    if (location.pathname === "/" && !location.hash) {
      navigate("/#journals", { replace: true, preventScrollReset: true });
    }
  }, [location, navigate]);
  
  const handleSearch = async () => {
    const resultsUrl = buildResultsUrl({ rowSelection, date, searchTerm });
    navigate(resultsUrl);
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
    [journals, rowSelection, setRowSelection],
  );

  const rangeContent = useMemo(
    () => <RangePage date={date} onDateChange={setDate} />,
    [date],
  );

  const searchContent = useMemo(
    () => (
      <SearchPage searchTerm={searchTerm} onSearchTermChange={setSearchTerm} />
    ),
    [searchTerm],
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
