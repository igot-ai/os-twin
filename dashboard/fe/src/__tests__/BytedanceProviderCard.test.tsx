import { render, screen, fireEvent } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import '@testing-library/jest-dom';
import { BytedanceProviderCard } from '../components/settings/BytedanceProviderCard';
import type { ProviderSettings } from '../types/settings';

describe('BytedanceProviderCard', () => {
  const mockOnSettingsChange = vi.fn();
  const mockOnVaultClick = vi.fn();

  const defaultProvider: ProviderSettings = {
    enabled: true,
    base_url: 'ap-southeast-1',
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders Bytedance (Ark) header', () => {
    render(
      <BytedanceProviderCard
        provider={defaultProvider}
        onSettingsChange={mockOnSettingsChange}
        onVaultClick={mockOnVaultClick}
        vaultSet={false}
      />
    );

    expect(screen.getByText('Bytedance (Ark)')).toBeInTheDocument();
  });

  it('shows READY status when enabled', () => {
    render(
      <BytedanceProviderCard
        provider={defaultProvider}
        onSettingsChange={mockOnSettingsChange}
        onVaultClick={mockOnVaultClick}
        vaultSet={true}
      />
    );

    expect(screen.getByText('READY')).toBeInTheDocument();
  });

  it('shows INACTIVE status when disabled', () => {
    const disabledProvider: ProviderSettings = { enabled: false };
    render(
      <BytedanceProviderCard
        provider={disabledProvider}
        onSettingsChange={mockOnSettingsChange}
        onVaultClick={mockOnVaultClick}
        vaultSet={false}
      />
    );

    expect(screen.getByText('INACTIVE')).toBeInTheDocument();
  });

  it('displays "API Key: Configured" when vaultSet is true', () => {
    render(
      <BytedanceProviderCard
        provider={defaultProvider}
        onSettingsChange={mockOnSettingsChange}
        onVaultClick={mockOnVaultClick}
        vaultSet={true}
      />
    );

    expect(screen.getByText('API Key: Configured')).toBeInTheDocument();
  });

  it('does not display "API Key: Configured" when vaultSet is false', () => {
    render(
      <BytedanceProviderCard
        provider={defaultProvider}
        onSettingsChange={mockOnSettingsChange}
        onVaultClick={mockOnVaultClick}
        vaultSet={false}
      />
    );

    expect(screen.queryByText('API Key: Configured')).not.toBeInTheDocument();
  });

  it('displays selected region in status', () => {
    render(
      <BytedanceProviderCard
        provider={defaultProvider}
        onSettingsChange={mockOnSettingsChange}
        onVaultClick={mockOnVaultClick}
        vaultSet={false}
      />
    );

    expect(screen.getByText('Region: ap-southeast-1')).toBeInTheDocument();
  });

  it('renders region selection button', () => {
    render(
      <BytedanceProviderCard
        provider={defaultProvider}
        onSettingsChange={mockOnSettingsChange}
        onVaultClick={mockOnVaultClick}
        vaultSet={false}
      />
    );

    expect(screen.getByText('Singapore')).toBeInTheDocument();
    expect(screen.getByText('SG')).toBeInTheDocument();
  });

  it('calls onSettingsChange when region is clicked', () => {
    render(
      <BytedanceProviderCard
        provider={{ enabled: true }}
        onSettingsChange={mockOnSettingsChange}
        onVaultClick={mockOnVaultClick}
        vaultSet={false}
      />
    );

    fireEvent.click(screen.getByText('Singapore'));
    expect(mockOnSettingsChange).toHaveBeenCalledWith({ base_url: 'ap-southeast-1' });
  });

  it('highlights selected region button', () => {
    render(
      <BytedanceProviderCard
        provider={defaultProvider}
        onSettingsChange={mockOnSettingsChange}
        onVaultClick={mockOnVaultClick}
        vaultSet={false}
      />
    );

    const singaporeButton = screen.getByText('Singapore').closest('button');
    expect(singaporeButton).toHaveClass('border-slate-300');
    expect(singaporeButton).toHaveClass('bg-slate-50');
  });

  it('displays placeholder text when vaultSet is false', () => {
    render(
      <BytedanceProviderCard
        provider={defaultProvider}
        onSettingsChange={mockOnSettingsChange}
        onVaultClick={mockOnVaultClick}
        vaultSet={false}
      />
    );

    expect(screen.getByText('Enter Bytedance Access Token')).toBeInTheDocument();
  });

  it('displays masked key when vaultSet is true', () => {
    render(
      <BytedanceProviderCard
        provider={defaultProvider}
        onSettingsChange={mockOnSettingsChange}
        onVaultClick={mockOnVaultClick}
        vaultSet={true}
      />
    );

    expect(screen.getByText('\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022')).toBeInTheDocument();
  });

  it('calls onVaultClick when API key button is clicked', () => {
    render(
      <BytedanceProviderCard
        provider={defaultProvider}
        onSettingsChange={mockOnSettingsChange}
        onVaultClick={mockOnVaultClick}
        vaultSet={false}
      />
    );

    fireEvent.click(screen.getByText('Enter Bytedance Access Token'));
    expect(mockOnVaultClick).toHaveBeenCalledTimes(1);
  });

  it('renders documentation link', () => {
    render(
      <BytedanceProviderCard
        provider={defaultProvider}
        onSettingsChange={mockOnSettingsChange}
        onVaultClick={mockOnVaultClick}
        vaultSet={false}
      />
    );

    const learnMoreLink = screen.getByText('Learn More');
    expect(learnMoreLink).toBeInTheDocument();
    expect(learnMoreLink.closest('a')).toHaveAttribute('href', 'https://docs.byteplus.com/en/docs/ModelArk/1099455');
  });

  it('renders info panel with enterprise verification message', () => {
    render(
      <BytedanceProviderCard
        provider={defaultProvider}
        onSettingsChange={mockOnSettingsChange}
        onVaultClick={mockOnVaultClick}
        vaultSet={false}
      />
    );

    expect(screen.getByText('Regional Optimization Required')).toBeInTheDocument();
    expect(screen.getByText(/valid enterprise verification/)).toBeInTheDocument();
  });

  it('defaults to enabled=false when provider is null/undefined', () => {
    render(
      <BytedanceProviderCard
        provider={null as unknown as ProviderSettings}
        onSettingsChange={mockOnSettingsChange}
        onVaultClick={mockOnVaultClick}
        vaultSet={false}
      />
    );

    expect(screen.getByText('INACTIVE')).toBeInTheDocument();
  });

  it('defaults base_url to cn-beijing-1 when not set', () => {
    render(
      <BytedanceProviderCard
        provider={{ enabled: true }}
        onSettingsChange={mockOnSettingsChange}
        onVaultClick={mockOnVaultClick}
        vaultSet={false}
      />
    );

    expect(screen.getByText('Region: cn-beijing-1')).toBeInTheDocument();
  });

  it('does not render test button or latency display (feature removed)', () => {
    render(
      <BytedanceProviderCard
        provider={defaultProvider}
        onSettingsChange={mockOnSettingsChange}
        onVaultClick={mockOnVaultClick}
        vaultSet={true}
      />
    );

    expect(screen.queryByText('[RUN TEST]')).not.toBeInTheDocument();
    expect(screen.queryByText(/LATENCY/)).not.toBeInTheDocument();
    expect(screen.queryByText('TESTING...')).not.toBeInTheDocument();
  });
});
