import { cn } from "@/lib/utils";
import { PRODUCT_NAME } from "@/lib/product";

/** The mark: a desk bell inside a rounded tile, the front desk's sign. */
export function BrandMark({ className }: { className?: string }) {
  return (
    <span className={cn("grid size-8 shrink-0 place-items-center rounded-lg bg-primary text-primary-foreground shadow-sm", className)}>
      <svg viewBox="0 0 24 24" className="size-[18px]" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
        <path d="M12 6V4.5M10 4.5h4" />
        <path d="M4.5 16a7.5 7.5 0 0 1 15 0" />
        <path d="M3 19h18" />
      </svg>
    </span>
  );
}

export function Brand({ className }: { className?: string }) {
  return (
    <div className={cn("flex items-center gap-2.5", className)}>
      <BrandMark />
      <span className="text-base font-semibold tracking-tight">{PRODUCT_NAME}</span>
    </div>
  );
}
