// The frame of every signed-out page: the brand panel on the left (wide
// screens), the task on the right. On phones only a slim header stays.
import type { ReactNode } from "react";
import { Brand } from "@/components/app/brand";
import { ThemeMenu } from "@/components/app/theme-menu";
import { PRODUCT_NAME } from "@/lib/product";
import { BrandPanel } from "./brand-panel";

export function AuthFrame({ children }: { children: ReactNode }) {
  return (
    <div className="grid min-h-screen lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
      <BrandPanel />
      <div className="flex min-h-screen flex-col">
        <header className="flex items-center justify-between px-4 py-4 sm:px-8">
          <Brand className="lg:invisible" />
          <ThemeMenu />
        </header>
        <main className="flex flex-1 items-center justify-center px-4 py-10 sm:px-8">
          <div className="w-full max-w-sm">{children}</div>
        </main>
        <footer className="px-4 py-6 text-center text-xs text-muted-foreground sm:px-8">
          © {new Date().getFullYear()} {PRODUCT_NAME}
        </footer>
      </div>
    </div>
  );
}
