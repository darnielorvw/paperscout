import type { ReactNode } from "react";
import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router";

import { ArrowDownIcon, ArrowUpIcon, CheckIcon } from "lucide-react";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
} from "~/components/ui/accordion";
import { Button } from "./ui/button";

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
  const location = useLocation();
  const navigate = useNavigate();
  const hashItem = location.hash.replace("#", "");

  const [activeItem, setActiveItem] = useState<string | undefined>(
    hashItem || items[0]?.value,
  );
  const buttonRefs = useRef<(HTMLButtonElement | null)[]>([]);

  // Wenn sich der Hash in der URL ändert (z.B. durch Klick in der Sidebar),
  // synchronisieren wir den State des Accordions.
  useEffect(() => {
    if (hashItem && items.some((item) => item.value === hashItem)) {
      setActiveItem(hashItem);
    } else if (!hashItem) {
      setActiveItem(items[0]?.value);
    }
  }, [hashItem, items]);

  useEffect(() => {
    const index = items.findIndex((item) => item.value === activeItem);
    if (index !== -1) {
      // Ein kurzes Timeout stellt sicher, dass das Element im DOM gemountet 
      // und die Aufklapp-Animation gestartet ist, bevor es fokussiert wird.
      const timer = setTimeout(() => {
        buttonRefs.current[index]?.focus();
      }, 100);
      return () => clearTimeout(timer);
    }
  }, [activeItem, items]);

  // Hilfsfunktion: Setzt das Accordion & aktualisiert gleichzeitig die URL
  const updateActiveItem = (newValue: string | undefined) => {
    setActiveItem(newValue);
    navigate(newValue ? `#${newValue}` : "", { replace: true });
  };

  const handleNext = (currentIndex: number) => {
    const nextIndex = currentIndex + 1;
    if (nextIndex < items.length) {
      updateActiveItem(items[nextIndex].value);
    }
  };

  const handlePrevious = (currentIndex: number) => {
    const prevIndex = currentIndex - 1;
    if (prevIndex >= 0) {
      updateActiveItem(items[prevIndex].value);
    }
  };

  // Globale Tastatur-Navigation (Pfeil nach unten / oben)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ignoriere Tasteneingaben, wenn der Benutzer in einem Textfeld tippt
      const activeTag = document.activeElement?.tagName;
      if (activeTag === "INPUT" || activeTag === "TEXTAREA") {
        return;
      }

      const currentIndex = items.findIndex((item) => item.value === activeItem);
      if (currentIndex === -1) return;

      if (e.key === "ArrowDown" && currentIndex < items.length - 1) {
        e.preventDefault();
        updateActiveItem(items[currentIndex + 1].value);
      } else if (e.key === "ArrowUp" && currentIndex > 0) {
        e.preventDefault();
        updateActiveItem(items[currentIndex - 1].value);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [activeItem, items]); // Abhängigkeiten für aktuelles Item und Liste

  return (
    <Accordion
      type="single"
      collapsible
      value={activeItem}
      onValueChange={updateActiveItem}
      className="flex h-full w-full flex-col"
    >
      {items.map((item, index) => (
        <AccordionItem
          key={item.value}
          value={item.value}
          className="flex flex-col data-[state=open]:flex-1 overflow-hidden [&[data-state=open]>[data-slot=accordion-content]]:flex [&[data-state=open]>[data-slot=accordion-content]]:flex-1 [&[data-state=open]>[data-slot=accordion-content]]:flex-col"
        >
          <div className="flex items-start py-2.5 text-left text-sm font-medium">
            {item.trigger}
          </div>
          <AccordionContent className="flex flex-1 flex-col overflow-auto min-h-0">
            {item.content}
            <div className="mt-auto flex justify-center gap-4 p-4">
              {index > 0 && (
                <Button className="rounded-full" variant="outline" onClick={() => handlePrevious(index)} size="icon-xl">
                  <ArrowUpIcon className="size-6" />
                </Button>
              )}
              {index < items.length - 1 ? (
                <Button
                  ref={(el) => {
                    buttonRefs.current[index] = el;
                  }}
                  className="rounded-full"
                  onClick={() => handleNext(index)}
                  size="icon-xl"
                >
                  <ArrowDownIcon className="size-6" />
                </Button>
              ) : (
                <Button
                  ref={(el) => {
                    buttonRefs.current[index] = el;
                  }}
                  className="rounded-full"
                  variant="default"
                  onClick={() => console.log("Fertig!")}
                  size="icon-xl"
                >
                  <CheckIcon className="size-6" />
                </Button>
              )}
            </div>
          </AccordionContent>
        </AccordionItem>
      ))}
    </Accordion>
  );
}
