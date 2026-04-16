import { render, screen, fireEvent } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import '@testing-library/jest-dom';
import { DynamicProviderCard } from '../components/settings/DynamicProviderCard';
import type { ConfiguredProvider, ProviderSettings } from '../types/settings';

const mockProvider: ConfiguredProvider = {
  id: 'deepseek',
  name: 'DeepSeek',
  doc: 'https://docs.deepseek.com',
  api: 'https://api.deepseek.com',
  npm: '',
  env: ['DEEPSEEK_API_KEY'],
  logo_url: 'https://models.dev/logos/deepseek.svg',
  source: 'auth.json',
  models: {
    'deepseek-chat': {
      id: 'deepseek-chat',
      name: 'DeepSeek Chat',
      family: 'chat',
      reasoning: false,
      tool_call: true,
      attachment: false,
      temperature: true,
      cost: {},
      limit: {},
      modalities: {},
      knowledge: '',
      release_date: '',
    },
    'deepseek-reasoner': {
      id: 'deepseek-reasoner',
      name: 'DeepSeek Reasoner',
      family: 'reasoning',
      reasoning: true,
      tool_call: false,
      attachment: false,
      temperature: true,
      cost: {},
      limit: {},
      modalities: {},
      knowledge: '',
      release_date: '',
    },
  },
};

const mockProviderWithoutEnv: ConfiguredProvider = {
  ...mockProvider,
  id: 'xai',
  name: 'xAI',
  env: [],
  models: {},
};

describe('DynamicProviderCard', () => {
  const mockOnVaultClick = vi.fn();
  const mockOnToggle = vi.fn();
  const mockOnRemove = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders provider name and model count', () => {
    render(
      <DynamicProviderCard
        providerId="deepseek"
        provider={mockProvider}
        vaultSet={true}
        onVaultClick={mockOnVaultClick}
        onToggle={mockOnToggle}
      />
    );

    expect(screen.getByText('DeepSeek')).toBeInTheDocument();
    expect(screen.getByText(/2 models/)).toBeInTheDocument();
  });

  it('shows ACTIVE status when vaultSet is true and enabled', () => {
    const settings: ProviderSettings = { enabled: true };
    render(
      <DynamicProviderCard
        providerId="deepseek"
        provider={mockProvider}
        settings={settings}
        vaultSet={true}
        onVaultClick={mockOnVaultClick}
        onToggle={mockOnToggle}
      />
    );

    expect(screen.getByText('ACTIVE')).toBeInTheDocument();
    expect(screen.getByText('READY')).toBeInTheDocument();
  });

  it('shows INACTIVE status when vaultSet is false', () => {
    const settings: ProviderSettings = { enabled: true };
    render(
      <DynamicProviderCard
        providerId="deepseek"
        provider={mockProvider}
        settings={settings}
        vaultSet={false}
        onVaultClick={mockOnVaultClick}
        onToggle={mockOnToggle}
      />
    );

    const statusBadges = screen.getAllByText('INACTIVE');
    expect(statusBadges.length).toBeGreaterThan(0);
  });

  it('shows INACTIVE status when disabled', () => {
    const settings: ProviderSettings = { enabled: false };
    render(
      <DynamicProviderCard
        providerId="deepseek"
        provider={mockProvider}
        settings={settings}
        vaultSet={true}
        onVaultClick={mockOnVaultClick}
        onToggle={mockOnToggle}
      />
    );

    const statusBadges = screen.getAllByText('INACTIVE');
    expect(statusBadges.length).toBeGreaterThan(0);
  });

  it('displays masked API key when vaultSet is true', () => {
    render(
      <DynamicProviderCard
        providerId="deepseek"
        provider={mockProvider}
        vaultSet={true}
        onVaultClick={mockOnVaultClick}
        onToggle={mockOnToggle}
      />
    );

    expect(screen.getByText('\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022')).toBeInTheDocument();
  });

  it('displays "Click to configure" when vaultSet is false', () => {
    render(
      <DynamicProviderCard
        providerId="deepseek"
        provider={mockProvider}
        vaultSet={false}
        onVaultClick={mockOnVaultClick}
        onToggle={mockOnToggle}
      />
    );

    expect(screen.getByText('Click to configure')).toBeInTheDocument();
  });

  it('calls onVaultClick when API key button is clicked', () => {
    render(
      <DynamicProviderCard
        providerId="deepseek"
        provider={mockProvider}
        vaultSet={false}
        onVaultClick={mockOnVaultClick}
        onToggle={mockOnToggle}
      />
    );

    fireEvent.click(screen.getByText('Click to configure'));
    expect(mockOnVaultClick).toHaveBeenCalledTimes(1);
  });

  it('displays env var hint when provider has env vars', () => {
    render(
      <DynamicProviderCard
        providerId="deepseek"
        provider={mockProvider}
        vaultSet={true}
        onVaultClick={mockOnVaultClick}
        onToggle={mockOnToggle}
      />
    );

    expect(screen.getByText(/ENV:/)).toBeInTheDocument();
    expect(screen.getByText('DEEPSEEK_API_KEY')).toBeInTheDocument();
  });

  it('hides env var hint when provider has no env vars', () => {
    render(
      <DynamicProviderCard
        providerId="xai"
        provider={mockProviderWithoutEnv}
        vaultSet={true}
        onVaultClick={mockOnVaultClick}
        onToggle={mockOnToggle}
      />
    );

    expect(screen.queryByText(/ENV:/)).not.toBeInTheDocument();
  });

  it('displays documentation link when provider has doc URL', () => {
    render(
      <DynamicProviderCard
        providerId="deepseek"
        provider={mockProvider}
        vaultSet={true}
        onVaultClick={mockOnVaultClick}
        onToggle={mockOnToggle}
      />
    );

    const docLink = screen.getByText('Documentation');
    expect(docLink).toBeInTheDocument();
    expect(docLink.closest('a')).toHaveAttribute('href', 'https://docs.deepseek.com');
  });

  it('hides documentation link when provider has no doc URL', () => {
    const providerNoDoc = { ...mockProvider, doc: '' };
    render(
      <DynamicProviderCard
        providerId="deepseek"
        provider={providerNoDoc}
        vaultSet={true}
        onVaultClick={mockOnVaultClick}
        onToggle={mockOnToggle}
      />
    );

    expect(screen.queryByText('Documentation')).not.toBeInTheDocument();
  });

  it('displays remove button when onRemove is provided', () => {
    render(
      <DynamicProviderCard
        providerId="deepseek"
        provider={mockProvider}
        vaultSet={true}
        onVaultClick={mockOnVaultClick}
        onToggle={mockOnToggle}
        onRemove={mockOnRemove}
      />
    );

    expect(screen.getByTitle('Remove provider')).toBeInTheDocument();
  });

  it('hides remove button when onRemove is not provided', () => {
    render(
      <DynamicProviderCard
        providerId="deepseek"
        provider={mockProvider}
        vaultSet={true}
        onVaultClick={mockOnVaultClick}
        onToggle={mockOnToggle}
      />
    );

    expect(screen.queryByTitle('Remove provider')).not.toBeInTheDocument();
  });

  it('calls onRemove when remove button is clicked', () => {
    render(
      <DynamicProviderCard
        providerId="deepseek"
        provider={mockProvider}
        vaultSet={true}
        onVaultClick={mockOnVaultClick}
        onToggle={mockOnToggle}
        onRemove={mockOnRemove}
      />
    );

    fireEvent.click(screen.getByTitle('Remove provider'));
    expect(mockOnRemove).toHaveBeenCalledTimes(1);
  });

  it('defaults to enabled when settings not provided', () => {
    render(
      <DynamicProviderCard
        providerId="deepseek"
        provider={mockProvider}
        vaultSet={true}
        onVaultClick={mockOnVaultClick}
        onToggle={mockOnToggle}
      />
    );

    expect(screen.getByText('ACTIVE')).toBeInTheDocument();
  });

  it('does not render test button or latency display (feature removed)', () => {
    render(
      <DynamicProviderCard
        providerId="deepseek"
        provider={mockProvider}
        vaultSet={true}
        onVaultClick={mockOnVaultClick}
        onToggle={mockOnToggle}
      />
    );

    expect(screen.queryByText('[TEST]')).not.toBeInTheDocument();
    expect(screen.queryByText(/LATENCY/)).not.toBeInTheDocument();
    expect(screen.queryByText('TESTING...')).not.toBeInTheDocument();
  });
});
