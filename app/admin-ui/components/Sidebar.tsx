import Link from "next/link";

const NAV = [
  { href: "/", label: "Overview" },
  { href: "/tenants", label: "Tenants" },
  { href: "/usage", label: "Usage" },
  { href: "/recent", label: "Recent" },
  { href: "/grafana", label: "Grafana" },
];

export default function Sidebar() {
  return (
    <aside className="w-56 border-r border-border bg-panel/60 p-4 shrink-0 min-h-screen">
      <Link href="/" className="block mb-6">
        <div className="text-lg font-semibold">LLM Gateway</div>
        <div className="text-xs text-muted">admin console</div>
      </Link>
      <nav className="flex flex-col gap-1">
        {NAV.map((n) => (
          <Link
            key={n.href}
            href={n.href}
            className="px-3 py-2 rounded-md text-sm hover:bg-[#1a1f2a] text-muted hover:text-white transition-colors"
          >
            {n.label}
          </Link>
        ))}
      </nav>
      <div className="absolute bottom-4 text-[10px] text-muted/60">
        v0.1 · server-side admin proxy
      </div>
    </aside>
  );
}
