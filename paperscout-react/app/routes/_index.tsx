// app/routes/_index.tsx
import { InputAccordion } from "~/components/input-accordion";
import JournalsPage from "~/pages/journals/journals";


export default function Home() {
  const accordionItems = [
    {
      value: "journals",
      trigger: "Search for Journals",
      content: <JournalsPage/> 
    },
    {
      value: "search",
      trigger: "Enter a Search Term",
      content: "Dies ist nur ein normaler Text-Inhalt."
    },
    {
      value: "logout",
      trigger: "Abmelden",
      content: "Dies ist nur ein normaler Text-Inhalt."}
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
