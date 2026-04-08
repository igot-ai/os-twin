import useSWR from 'swr';
import { apiGet } from '@/lib/api-client';
import { planCategories, type PlanCategory, type PromptTemplate } from '@/data/prompt-templates';

export type { PlanCategory, PromptTemplate };

export interface PromptSuggestion {
  id: string;
  text: string;
  icon: string;
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

export const mockHomeData: HomeData = {
  user: {
    name: 'Alex',
    workspace: 'Ostwin Pro',
  },
  categories: planCategories,
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
