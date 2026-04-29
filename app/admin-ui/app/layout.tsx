import "./globals.css";
import type { Metadata } from "next";
import Sidebar from "@/components/Sidebar";

export const metadata: Metadata = {
  title: "LLM Gateway · Admin",
  description: "Admin console for the LLM Gateway",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="font-mono">
        <div className="flex min-h-screen">
          <Sidebar />
          <main className="flex-1 p-8 max-w-[1400px]">{children}</main>
        </div>
      </body>
    </html>
  );
}
