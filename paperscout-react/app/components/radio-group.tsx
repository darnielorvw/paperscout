import { motion } from "framer-motion";
import { RadioGroup, RadioGroupItem } from "~/components/ui/radio-group";
import { FieldDescription, FieldLabel, FieldTitle } from "./ui/field";

export interface RadioItem {
  value: string;
  title: string;
  description?: string;
}

interface HorizontalRadioGroupProps {
  items: RadioItem[];
  value?: string;
  onValueChange?: (value: string) => void;
}

export function HorizontalRadioGroup({ items, value, onValueChange }: HorizontalRadioGroupProps) {
  return (
    <div className="overflow-x-auto py-1">
      <RadioGroup
        value={value}
        onValueChange={onValueChange}
        className="flex flex-row"
      >
        {items.map((item) => (
          <FieldLabel
            key={item.value}
            htmlFor={item.value}
            className="relative rounded-lg cursor-pointer border py-2 pl-2 transition-colors duration-200 select-none z-10 shrink-0"
          >
            <FieldTitle >{item.title}</FieldTitle>
            <FieldDescription>
              {item.description}
            </FieldDescription>
            <RadioGroupItem value={item.value} id={item.value} className="hidden" />
            {value === item.value && (
              <motion.div
                layoutId="active-bg"
                className="absolute inset-0  dark:bg-input rounded-lg -z-10"
                transition={{ type: "spring", stiffness: 380, damping: 40 }}
              />
            )}
          </FieldLabel>
        ))}
      </RadioGroup>
    </div>
  );
}