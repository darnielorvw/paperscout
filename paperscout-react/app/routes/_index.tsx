// app/routes/_index.tsx
import { InputAccordion } from "~/components/input-accordion";
import SearchPage from "~/pages/search/search";


export default function Home() {
  const accordionItems = [
    {
      value: "search-page",
      trigger: "Suche öffnen",
      content: <SearchPage/> 
    },
    {
      value: "help",
      trigger: "Hilfe & Info",
      content: "Dies ist nur ein normaler Text-Inhalt."
    }
  ];

  return (
    <div className="h-full w-full">
      <InputAccordion 
        title="PaperScout Dashboard" 
        description="Wähle eine Aktion aus dem Menü." 
        items={accordionItems} 
      />
    </div>
  );
}
