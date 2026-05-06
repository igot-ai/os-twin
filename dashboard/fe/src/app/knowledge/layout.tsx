import { Metadata } from 'next';

/**
 * Metadata for the global Knowledge page.
 * Provides SEO-friendly title and description for the standalone knowledge management interface.
 */
export const metadata: Metadata = {
  title: 'Knowledge Base | Ostwin',
  description: 'Manage knowledge namespaces, import documents, and query your knowledge base. Access your global knowledge management interface.',
  openGraph: {
    title: 'Knowledge Base | Ostwin',
    description: 'Manage knowledge namespaces, import documents, and query your knowledge base.',
    type: 'website',
  },
};

/**
 * Layout wrapper for the Knowledge page.
 * Provides metadata and any shared layout elements.
 */
export default function KnowledgeLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
