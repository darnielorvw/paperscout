import type { ReactNode } from "react";

import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "~/components/ui/accordion";

interface AccordionItemData {
  value: string;
  trigger: string;
  content: ReactNode;
}

interface InputAccordionProps {
  title?: string;
  description?: string;
  items: AccordionItemData[];
}

export function InputAccordion({ items }: InputAccordionProps) {
  return (
    <Accordion type="single" collapsible defaultValue={items[0]?.value}>
      {items.map((item) => (
        <AccordionItem key={item.value} value={item.value}>
          <AccordionTrigger>{item.trigger}</AccordionTrigger>
          <AccordionContent>{item.content}</AccordionContent>
        </AccordionItem>
      ))}
    </Accordion>
  );
}
