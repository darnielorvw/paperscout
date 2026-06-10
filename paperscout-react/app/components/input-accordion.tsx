import type { ReactNode } from "react"

import {
    Accordion,
    AccordionContent,
    AccordionItem,
    AccordionTrigger,
} from "~/components/ui/accordion"
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from "~/components/ui/card"

interface AccordionItemData {
  value: string
  trigger: string
  content: ReactNode
}

interface InputAccordionProps {
  title?: string
  description?: string
  items: AccordionItemData[]
}

export function InputAccordion({
  title = "Subscription & Billing",
  description = "Common questions about your account...",
  items
}: InputAccordionProps) {
  return (
    <Card className="w-full h-full flex flex-col">
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent>
        <Accordion type="single" collapsible defaultValue={items[0]?.value}>
          {items.map((item) => (
            <AccordionItem key={item.value} value={item.value}>
              <AccordionTrigger>{item.trigger}</AccordionTrigger>
              <AccordionContent>{item.content}</AccordionContent>
            </AccordionItem>
          ))}
        </Accordion>
      </CardContent>
    </Card>
  )
}
