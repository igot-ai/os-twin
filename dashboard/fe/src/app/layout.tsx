import type { Metadata } from "next";
// cache invalidation 1
import { Plus_Jakarta_Sans, IBM_Plex_Mono } from "next/font/google";
import "./globals.css";
import { SWRProvider } from "@/components/swr-provider";
import AppShell from "@/components/layout/AppShell";
import { AuthProvider } from "@/components/auth/AuthProvider";
import AuthOverlay from "@/components/auth/AuthOverlay";
import { WebSocketProvider } from "@/components/providers/WebSocketProvider";


const plusJakartaSans = Plus_Jakarta_Sans({
  subsets: ["latin"],
  variable: "--font-plus-jakarta-sans",
  display: "swap",
});

const ibmPlexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  variable: "--font-ibm-plex-mono",
  display: "swap",
  weight: ["400", "500"],
});

export const metadata: Metadata = {
  title: "⬡ OsTwin — Command Center",
  description: "Agentic OS Enterprise Command Center — Real-time plan management, agent orchestration, and operational intelligence",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning className={`${plusJakartaSans.variable} ${ibmPlexMono.variable}`}>
      <head>
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap"
        />
      </head>
      <body className="h-screen flex flex-col antialiased overflow-hidden" suppressHydrationWarning>
        <AuthProvider>
          <AuthOverlay />
          <WebSocketProvider>
            <SWRProvider>
              <AppShell>
                {children}
              </AppShell>
            </SWRProvider>
          </WebSocketProvider>
        </AuthProvider>
      </body>

    </html>
  );
}
