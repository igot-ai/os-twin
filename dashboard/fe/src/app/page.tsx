'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useHomeData } from '@/hooks/use-home-data';
import { usePlans } from '@/hooks/use-plans';
import PlanCard from '@/components/dashboard/PlanCard';
import { CommandPrompt } from '@/components/ui/CommandPrompt';
import { Skeleton } from '@/components/ui/Skeleton';
import { BrandIcon } from '@/components/ui/BrandIcon';
import { ActivityFeed } from '@/components/chat/ActivityFeed';
import type { ImageAttachment } from '@/types';

export default function DashboardHomePage() {
  const router = useRouter();
  const { data: homeData, isLoading: homeLoading } = useHomeData();
  const { plans, isLoading: plansLoading } = usePlans();
  
  const [prompt, setPrompt] = useState('');
  const [selectedSuggestionIndex, setSelectedSuggestionIndex] = useState(0);
  const [isCreatingThread, setIsCreatingThread] = useState(false);

  const handleSubmitPrompt = async (submittedPrompt: string, images?: ImageAttachment[]) => {
    try {
      setIsCreatingThread(true);
      const body: Record<string, unknown> = { message: submittedPrompt };
      if (images && images.length > 0) {
        body.images = images.map(img => ({ url: img.url, name: img.name, type: img.type }));
      }
      const resp = await fetch((process.env.NEXT_PUBLIC_API_BASE_URL || '/api') + '/plans/threads', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify(body)
      });
      
      if (!resp.ok) {
        throw new Error('Failed to create thread');
      }

      const data = await resp.json();
      router.push(`/ideas/${data.thread_id}`);
    } catch (err) {
      console.error(err);
      alert('Failed to create thread. Please try again.');
    } finally {
      setIsCreatingThread(false);
    }
  };

  const handleSuggestionClick = (text: string) => {
    setPrompt(text);
  };

  const cycleSuggestion = () => {
    if (homeData?.suggestions?.length) {
      setSelectedSuggestionIndex(prev => (prev + 1) % homeData.suggestions.length);
    }
  };

  return (
    <div className="min-h-[calc(100vh-theme(spacing.16))] flex flex-col items-center animate-in fade-in slide-in-from-bottom-4 duration-700 w-full relative pt-8 px-6 pb-24">
      {/* Top Center Workspace Badge */}
      <div className="flex items-center gap-2 px-4 py-2 bg-[var(--color-surface)] border border-[var(--color-border)] rounded-[var(--radius-full)] shadow-[var(--shadow-card)] mb-12">
        <BrandIcon size={24} />
        <span className="text-sm font-medium text-[var(--color-text-main)]">
          {homeLoading ? 'Loading...' : homeData?.user?.workspace || 'Workspace'}
        </span>
        <span className="material-symbols-outlined text-[var(--color-text-muted)] text-sm">expand_more</span>
      </div>

      <div className="w-full max-w-4xl flex flex-col items-center">
        {/* Greeting */}
        <div className="flex flex-col items-center text-center mb-6">
          <BrandIcon size={48} className="mb-4 text-primary" />
          <h1 className="text-[38px] md:text-[46px] lg:text-[54px] leading-tight font-[var(--font-display)] font-bold text-[var(--color-text-main)] tracking-tight">
            Hi {homeLoading ? '...' : homeData?.user?.name || 'there'}, what do you want to build?
          </h1>
        </div>

        <CommandPrompt
          value={prompt}
          onChange={setPrompt}
          onSubmit={handleSubmitPrompt}
          isConversationActive={false}
          isLoading={isCreatingThread}
        />

        {/* Example Prompts */}
        <div className="mt-8 flex flex-col items-center">
          <button 
            onClick={cycleSuggestion}
            className="text-sm font-medium text-[var(--color-text-muted)] hover:text-[var(--color-text-main)] flex items-center gap-1 transition-colors mb-4"
          >
            Try an example prompt <span className="material-symbols-outlined text-sm">sync</span>
          </button>
          <div className="flex justify-center min-h-[40px]">
            {homeLoading ? (
              <Skeleton className="h-8 w-64 rounded-[var(--radius-full)]" />
            ) : homeData?.suggestions && homeData.suggestions.length > 0 ? (
              <button 
                onClick={() => handleSuggestionClick(homeData.suggestions[selectedSuggestionIndex].text)}
                className="px-4 py-2 bg-[var(--color-surface)] border border-[var(--color-border)] rounded-[var(--radius-full)] text-sm text-[var(--color-text-main)] hover:border-[var(--color-primary)] hover:text-primary transition-all shadow-[var(--shadow-card)] hover:shadow-[var(--shadow-card-hover)] flex items-center gap-2 animate-in fade-in duration-300"
                key={homeData.suggestions[selectedSuggestionIndex].id}
              >
                <span className="material-symbols-outlined text-sm text-[var(--color-text-muted)]">
                  {homeData.suggestions[selectedSuggestionIndex].icon}
                </span>
                {homeData.suggestions[selectedSuggestionIndex].text}
              </button>
            ) : null}
          </div>
        </div>

        {/* Plan Type Carousel */}
        <div className="w-full mt-12 mb-16 relative">
          <div className="flex items-center gap-4 overflow-x-auto pb-4 hide-scrollbar snap-x snap-mandatory">
            {homeLoading ? (
              Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="min-w-[120px] h-[100px] rounded-[var(--radius-xl)] shrink-0" />
              ))
            ) : (
              homeData?.categories?.map(category => (
                <button 
                  key={category.id}
                  onClick={() => setPrompt(`Build a ${category.name.toLowerCase()} `)}
                  className="flex flex-col items-center justify-center p-4 bg-[var(--color-surface)] border border-[var(--color-border)] rounded-[var(--radius-xl)] min-w-[120px] shrink-0 snap-start hover:border-[var(--color-primary)] hover:shadow-[var(--shadow-card-hover)] transition-all group"
                >
                  <div className="w-12 h-12 bg-[var(--color-background)] rounded-full flex items-center justify-center mb-3 group-hover:bg-[var(--color-primary-muted)] transition-colors">
                    <span className="material-symbols-outlined text-[var(--color-text-muted)] group-hover:text-primary">
                      {category.icon}
                    </span>
                  </div>
                  <span className="text-sm font-medium text-[var(--color-text-main)]">{category.name}</span>
                </button>
              ))
            )}
          </div>
        </div>

        {/* Recent Projects & Activity */}
        <div className="w-full max-w-5xl">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-lg font-bold text-[var(--color-text-main)]">Your recent Plans</h2>
                <Link href="/plans" className="text-sm font-medium text-primary hover:text-[var(--color-primary-hover)] flex items-center gap-1 transition-colors">
                  View All <span className="material-symbols-outlined text-sm">arrow_forward</span>
                </Link>
              </div>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {plansLoading ? (
                  Array.from({ length: 2 }).map((_, i) => (
                    <div key={i} className="h-[200px]">
                      <Skeleton className="w-full h-full rounded-[var(--radius-xl)]" />
                    </div>
                  ))
                ) : plans && plans.length > 0 ? (
                  plans.slice(0, 2).map(plan => (
                    <PlanCard key={plan.plan_id} plan={plan} />
                  ))
                ) : (
                  <div className="col-span-full py-8 text-center bg-[var(--color-surface)] rounded-[var(--radius-xl)] border border-dashed border-[var(--color-border)]">
                    <p className="text-[var(--color-text-muted)]">No recent plans found. Start a new one above!</p>
                  </div>
                )}
              </div>
            </div>

            <div className="h-[400px]">
              <ActivityFeed />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

