import useSWR from 'swr';
import { apiGet } from '@/lib/api-client';

export interface PromptSuggestion {
  id: string;
  text: string;
  icon: string;
}

export interface PlanCategory {
  id: string;
  name: string;
  icon: string;
  description: string;
}

export interface HomeData {
  user: {
    name: string;
    avatar?: string;
    workspace: string;
  };
  categories: PlanCategory[];
  suggestions: PromptSuggestion[];
}

const mockHomeData: HomeData = {
  user: {
    name: 'Alex',
    workspace: 'Ostwin Pro',
  },
  categories: [
    { id: 'web', name: 'Web App', icon: 'web', description: 'Create a responsive web application' },
    { id: 'mobile', name: 'Mobile App', icon: 'smartphone', description: 'Build a cross-platform mobile app' },
    { id: 'backend', name: 'Backend API', icon: 'api', description: 'Develop a scalable REST or GraphQL API' },
    { id: 'data', name: 'Data Pipeline', icon: 'database', description: 'Setup an ETL pipeline' },
    { id: 'bot', name: 'AI Discord Bot', icon: 'smart_toy', description: 'Deploy an interactive agent' },
    { id: 'automation', name: 'Automation', icon: 'autorenew', description: 'Automate business workflows' },
  ],
  suggestions: [
    { id: 's1', text: 'Build a Next.js landing page with Tailwind CSS', icon: 'auto_awesome' },
    { id: 's2', text: 'Set up a Node.js Express server with MongoDB', icon: 'memory' },
    { id: 's3', text: 'Create a Python script to scrape a website', icon: 'code' },
    { id: 's4', text: 'Design a PostgreSQL database schema for an e-commerce store', icon: 'schema' },
    { id: 's5', text: 'Deploy a Telegram bot that answers FAQs', icon: 'chat' },
  ],
};

export function useHomeData() {
  const { data, error, isLoading } = useSWR<HomeData>('/home', apiGet, {
    fallbackData: mockHomeData,
  });

  return {
    data: data || mockHomeData,
    isLoading,
    isError: error,
  };
}
