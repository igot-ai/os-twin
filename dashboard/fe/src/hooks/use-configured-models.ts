'use client';

import useSWR from 'swr';
import { fetcher, apiPost } from '@/lib/api-client';
import type {
  ConfiguredModelsResponse,
  ConfiguredProvider,
  ConfiguredModel,
  ModelInfo,
  ModelSource,
  ProviderSummary,
} from '@/types/settings';

/**
 * Fetches the full configured models catalog (models.dev filtered by auth.json).
 */
export function useConfiguredModels() {
  const { data, error, isLoading, mutate } = useSWR<ConfiguredModelsResponse>(
    '/models/configured',
    fetcher,
    { revalidateOnFocus: false, dedupingInterval: 60_000 },
  );

  const reload = async () => {
    await apiPost('/models/reload');
    await mutate();
  };

  // Build a flat list of all models across all providers for select boxes
  const allModels: ModelInfo[] = [];
  if (data?.providers) {
    for (const [providerId, provider] of Object.entries(data.providers)) {
      for (const [modelId, model] of Object.entries(provider.models)) {
        allModels.push(toModelInfo(providerId, provider, modelId, model));
      }
    }
  }

  // Build registry grouped by provider display name (backward compat)
  const registry: Record<string, ModelInfo[]> = {};
  if (data?.providers) {
    for (const [providerId, provider] of Object.entries(data.providers)) {
      const displayName = provider.name;
      registry[displayName] = Object.entries(provider.models).map(
        ([modelId, model]) => toModelInfo(providerId, provider, modelId, model),
      );
    }
  }

  return {
    configured: data,
    providers: data?.providers ?? {},
    providerIds: data?.configured_provider_ids ?? [],
    allModels,
    registry,
    isLoading,
    isError: !!error,
    reload,
    mutate,
  };
}

/**
 * Fetches the list of configured providers with summary info.
 */
export function useConfiguredProviders() {
  const { data, error, isLoading } = useSWR<{ providers: ProviderSummary[] }>(
    '/models/providers',
    fetcher,
    { revalidateOnFocus: false },
  );

  return {
    providers: data?.providers ?? [],
    isLoading,
    isError: !!error,
  };
}

function toModelInfo(
  providerId: string,
  provider: ConfiguredProvider,
  modelId: string,
  model: ConfiguredModel,
): ModelInfo {
  // Companion models (google-vertex/*, google-vertex-anthropic/*) already carry
  // the companion-provider prefix in their modelId key — do not add providerId on
  // top.  All other providers need the "providerId/modelId" composite to match
  // what the /api/models/registry endpoint (and the test endpoint) expect.
  const registryId = model.companion_provider ? modelId : `${providerId}/${modelId}`;

  return {
    id: registryId,
    label: model.name,
    context_window: model.limit?.context
      ? formatContextWindow(model.limit.context)
      : '',
    tier: classifyTier(model),
    provider_id: model.companion_provider || providerId,
    family: model.family,
    cost: model.cost,
    logo_url: provider.logo_url,
    reasoning: model.reasoning,
    tool_call: model.tool_call,
    attachment: model.attachment,
    source: (model.source as ModelSource) ?? 'models.dev',
  };
}

function formatContextWindow(ctx: number): string {
  if (ctx >= 1_000_000) {
    const val = ctx / 1_000_000;
    return `${val % 1 === 0 ? val : val.toFixed(1)}M`;
  }
  if (ctx >= 1_000) {
    const val = ctx / 1_000;
    return `${val % 1 === 0 ? val : val.toFixed(1)}K`;
  }
  return String(ctx);
}

function classifyTier(model: ConfiguredModel): string {
  if (model.reasoning) return 'reasoning';
  const inputCost = model.cost?.input ?? 0;
  if (inputCost >= 10) return 'flagship';
  if (inputCost >= 1) return 'balanced';
  if (inputCost > 0) return 'fast';
  return 'unknown';
}
