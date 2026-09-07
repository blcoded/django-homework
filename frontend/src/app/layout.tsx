import type { Metadata } from "next";
import "./globals.css";
import { AppShell } from "@/components/navigation/app-shell";
import { AuthProvider } from "@/context/auth-context";

export const metadata: Metadata = {
  title: "RoommateOS — Shared Household Chores",
  description: "Automated, fair, and fun chore rotation for roommates.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased">
        <AuthProvider>
          <AppShell>{children}</AppShell>
        </AuthProvider>
      </body>
    </html>
  );
}
