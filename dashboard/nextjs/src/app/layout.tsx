import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "⬡ Agent OS — Command Center",
  description: "OS Twin Command Center Dashboard — Real-time war-room monitoring and plan management",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" data-theme="dark" suppressHydrationWarning>
      <body suppressHydrationWarning>{children}</body>
    </html>
  );
}
