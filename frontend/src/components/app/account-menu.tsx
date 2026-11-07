"use client";
// Who is signed in, and the way out. Sidebar: a full-width account button at
// the bottom (initial, email, role). Phone top bar: just the initial. Either
// opens a small menu; "Sign out" there asks first (SignOutDialog).
import { useState } from "react";
import { ChevronsUpDown, LogOut } from "lucide-react";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";
import { SignOutDialog } from "./sign-out-dialog";

// The clinic's teal shell or the operator's slate one.
const TONES = {
  clinic: {
    button: "hover:bg-sidebar-accent data-[state=open]:bg-sidebar-accent",
    avatar: "bg-sidebar-primary/20 text-sidebar-primary ring-sidebar-primary/30",
    name: "text-sidebar-accent-foreground",
  },
  ops: {
    button: "hover:bg-ops-accent data-[state=open]:bg-ops-accent",
    avatar: "bg-ops-primary/20 text-ops-primary ring-ops-primary/30",
    name: "text-ops-accent-foreground",
  },
} as const;

function Avatar({ email, className }: { email: string; className?: string }) {
  return (
    <span aria-hidden className={cn("grid size-8 shrink-0 place-items-center rounded-full text-sm font-semibold uppercase ring-1", className)}>
      {email.charAt(0)}
    </span>
  );
}

export function AccountMenu({ email, role, tone, compact = false }: {
  email: string; role: string; tone: keyof typeof TONES; compact?: boolean;
}) {
  const [asking, setAsking] = useState(false);
  const t = TONES[tone];
  return (
    <>
      {/* modal={false}: a modal menu opening a dialog can leave the page unclickable (Radix). */}
      <DropdownMenu modal={false}>
        <DropdownMenuTrigger
          aria-label={`Account: ${email}`}
          className={cn(
            "flex items-center gap-3 rounded-lg text-left transition-colors outline-none focus-visible:ring-2 focus-visible:ring-ring/60",
            compact ? "p-1" : "w-full px-2 py-2",
            t.button,
          )}
        >
          <Avatar email={email} className={t.avatar} />
          {!compact && (
            <>
              <span className="min-w-0 flex-1">
                <span className={cn("block truncate text-sm font-medium", t.name)} title={email}>{email}</span>
                <span className="block text-xs">{role}</span>
              </span>
              <ChevronsUpDown className="size-4 shrink-0 opacity-60" aria-hidden />
            </>
          )}
        </DropdownMenuTrigger>
        <DropdownMenuContent side={compact ? "bottom" : "top"} align={compact ? "end" : "start"} sideOffset={8}
          className={cn("p-1.5", compact ? "w-64" : "w-(--radix-dropdown-menu-trigger-width) min-w-56")}>
          <DropdownMenuLabel className="flex items-center gap-3 px-2 py-2 font-normal">
            <Avatar email={email} className="bg-primary/10 text-primary ring-primary/20" />
            <span className="min-w-0">
              <span className="block truncate text-sm font-medium text-foreground">{email}</span>
              <span className="block text-xs text-muted-foreground">{role}</span>
            </span>
          </DropdownMenuLabel>
          <DropdownMenuSeparator />
          <DropdownMenuItem variant="destructive" className="px-2 py-2" onSelect={() => setAsking(true)}>
            <LogOut /> Sign out
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
      <SignOutDialog email={email} open={asking} onOpenChange={setAsking} />
    </>
  );
}
