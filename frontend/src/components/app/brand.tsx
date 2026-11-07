import { PRODUCT_NAME } from "@/lib/product";
import { cn } from "@/lib/utils";

/** The glyph (Harsh's pick, 2026-11-07): a fine heartbeat line leading into
 *  bold voice bars, the clinic that answers by voice. Drawn in currentColor.
 *  src/app/icon.svg is the same drawing for the browser tab. */
export function BrandGlyph({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M1.8 12h2.9l1.9-4.2 2.8 8.6 2-4.4h1.6" strokeWidth="1.8" />
      <path d="M16.2 9.3v5.4M19.4 6.3v11.4M22.4 9.8v4.4" strokeWidth="2.7" />
    </svg>
  );
}

/** The mark: the glyph on a rounded tile. Tile colour comes from className. */
export function BrandMark({ className }: { className?: string }) {
  return (
    <span className={cn("grid size-8 shrink-0 place-items-center rounded-lg bg-primary text-primary-foreground shadow-sm", className)}>
      <BrandGlyph className="size-[62%]" />
    </span>
  );
}

export function Brand({ className, markClassName, size = "md" }: {
  className?: string; markClassName?: string; size?: "md" | "lg";
}) {
  const lg = size === "lg";
  return (
    <div className={cn("flex items-center", lg ? "gap-3" : "gap-2.5", className)}>
      <BrandMark className={cn(lg && "size-11 rounded-xl", markClassName)} />
      <span className={cn("font-semibold tracking-tight", lg ? "text-[22px]" : "text-base")}>{PRODUCT_NAME}</span>
    </div>
  );
}
