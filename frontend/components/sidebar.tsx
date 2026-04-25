"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard, Rss, Newspaper, Search, Upload,
  GitBranch, Shield, Bot, Zap,
} from "lucide-react";

const navItems = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/pipeline", label: "Pipeline", icon: GitBranch },
  { href: "/agents", label: "AI Team", icon: Bot },
  { href: "/newsletters", label: "Newsletters", icon: Newspaper },
  { href: "/sources", label: "Sources", icon: Rss },
  { href: "/search", label: "RAG Search", icon: Search },
  { href: "/upload", label: "Upload", icon: Upload },
  { href: "/governance", label: "Governance", icon: Shield },
];

export function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="w-56 border-r border-border bg-card flex flex-col py-4 px-2 shrink-0">
      <div className="px-3 mb-6">
        <div className="flex items-center gap-2">
          <Zap className="w-5 h-5 text-violet-400" />
          <span className="font-bold text-sm tracking-tight">Gen AI Digest</span>
        </div>
        <p className="text-[10px] text-muted-foreground mt-1">Powered by Groq + LangGraph</p>
      </div>

      <nav className="flex-1 space-y-1">
        {navItems.map(({ href, label, icon: Icon }) => (
          <Link
            key={href}
            href={href}
            className={cn(
              "flex items-center gap-2.5 px-3 py-2 rounded-md text-sm transition-colors",
              pathname === href
                ? "bg-violet-600/20 text-violet-300 font-medium"
                : "text-muted-foreground hover:text-foreground hover:bg-accent"
            )}
          >
            <Icon className="w-4 h-4" />
            {label}
          </Link>
        ))}
      </nav>

      <div className="px-3 mt-4 pt-4 border-t border-border">
        <p className="text-[10px] text-muted-foreground">
          Free tier stack<br />
          Groq · Supabase · Twilio
        </p>
      </div>
    </aside>
  );
}
