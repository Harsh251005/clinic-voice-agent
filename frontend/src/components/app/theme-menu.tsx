"use client";
// The Light / Dark / System switch, beside the problems bell on every page.
import { Monitor, Moon, Sun } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuLabel, DropdownMenuRadioGroup, DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { setTheme, useTheme, type ThemeChoice } from "@/lib/theme";
import { cn } from "@/lib/utils";

const CHOICES: { value: ThemeChoice; label: string; icon: typeof Sun }[] = [
  { value: "light", label: "Light", icon: Sun },
  { value: "dark", label: "Dark", icon: Moon },
  { value: "system", label: "Same as this computer", icon: Monitor },
];

export function ThemeMenu({ className }: { className?: string }) {
  const [choice, shown] = useTheme();
  const Icon = shown === "dark" ? Moon : Sun;
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" className={cn(className)} aria-label="Appearance" title="Appearance">
          <Icon />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuLabel>Appearance</DropdownMenuLabel>
        <DropdownMenuRadioGroup value={choice} onValueChange={(v) => setTheme(v as ThemeChoice)}>
          {CHOICES.map(({ value, label, icon: ChoiceIcon }) => (
            <DropdownMenuRadioItem key={value} value={value}>
              <ChoiceIcon className="size-4" aria-hidden /> {label}
            </DropdownMenuRadioItem>
          ))}
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
