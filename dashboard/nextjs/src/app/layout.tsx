import type { Metadata } from 'next';
import './globals.css';
import ClientShell from '@/components/layout/ClientShell';

export const metadata: Metadata = {
  title: '⬡ OS Twin — Command Center',
  description:
    'OS Twin Command Center Dashboard — Real-time war-room monitoring and plan management',
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" data-theme="dark" suppressHydrationWarning>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link
          href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body suppressHydrationWarning>
        <ClientShell>{children}</ClientShell>
      </body>
    </html>
  );
}
