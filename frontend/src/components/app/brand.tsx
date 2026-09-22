import { Stethoscope } from "lucide-react";
import { cn } from "@/lib/utils";

export function Brand({ className }: { className?: string }) {
  return (
    <div className={cn("flex items-center gap-2.5", className)}>
      <span className="grid size-8 place-items-center rounded-lg bg-primary text-primary-foreground">
        <Stethoscope className="size-4" aria-hidden />
      </span>
      <span className="text-[15px] font-semibold tracking-tight">
        Clinic <span className="text-primary">Console</span>
      </span>
    </div>
  );
}
