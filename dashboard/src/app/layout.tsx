import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Smart Contract Intelligence Scanner",
  description: "Live Web3 threat intelligence dashboard",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-slate-900 text-slate-200 antialiased">
        {children}
      </body>
    </html>
  );
}
