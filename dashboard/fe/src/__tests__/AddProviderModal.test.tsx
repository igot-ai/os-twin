import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import '@testing-library/jest-dom';
import { AddProviderModal } from '../components/settings/AddProviderModal';
import * as apiClient from '../lib/api-client';

vi.mock('../lib/api-client', () => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
}));

const mockProviders = [
  { id: 'anthropic', name: 'Anthropic', logo_url: '', model_count: 10, doc: '', env: ['ANTHROPIC_API_KEY'], already_configured: false },
  { id: 'byteplus', name: 'BytePlus', logo_url: '', model_count: 5, doc: '', env: [], already_configured: false },
  { id: 'deepseek', name: 'DeepSeek', logo_url: '', model_count: 8, doc: 'https://docs.deepseek.com', env: ['DEEPSEEK_API_KEY'], already_configured: false },
  { id: 'xai', name: 'xAI', logo_url: '', model_count: 3, doc: '', env: ['XAI_API_KEY'], already_configured: false },
  { id: 'openrouter', name: 'OpenRouter', logo_url: '', model_count: 100, doc: '', env: ['OPENROUTER_API_KEY'], already_configured: true },
  { id: 'zai', name: 'ZAI', logo_url: '', model_count: 15, doc: '', env: [], already_configured: false },
];

describe('AddProviderModal', () => {
  const mockOnClose = vi.fn();
  const mockOnProviderAdded = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    (apiClient.apiGet as ReturnType<typeof vi.fn>).mockResolvedValue({ providers: mockProviders });
    (apiClient.apiPost as ReturnType<typeof vi.fn>).mockResolvedValue({});
  });

  it('does not render when isOpen is false', () => {
    render(
      <AddProviderModal
        isOpen={false}
        onClose={mockOnClose}
        onProviderAdded={mockOnProviderAdded}
      />
    );

    expect(screen.queryByText('Add Provider')).not.toBeInTheDocument();
  });

  it('renders when isOpen is true', async () => {
    render(
      <AddProviderModal
        isOpen={true}
        onClose={mockOnClose}
        onProviderAdded={mockOnProviderAdded}
      />
    );

    expect(screen.getByText('Add Provider')).toBeInTheDocument();
    await waitFor(() => {
      expect(apiClient.apiGet).toHaveBeenCalledWith('/models/available');
    });
  });

  it('fetches providers from /models/available when opened', async () => {
    render(
      <AddProviderModal
        isOpen={true}
        onClose={mockOnClose}
        onProviderAdded={mockOnProviderAdded}
      />
    );

    await waitFor(() => {
      expect(apiClient.apiGet).toHaveBeenCalledWith('/models/available');
    });
  });

  it('excludes anthropic from the provider list (EXCLUDED_PROVIDER_IDS)', async () => {
    render(
      <AddProviderModal
        isOpen={true}
        onClose={mockOnClose}
        onProviderAdded={mockOnProviderAdded}
      />
    );

    await waitFor(() => {
      expect(screen.queryByText('Anthropic')).not.toBeInTheDocument();
    });
  });

  it('excludes byteplus from the provider list (EXCLUDED_PROVIDER_IDS)', async () => {
    render(
      <AddProviderModal
        isOpen={true}
        onClose={mockOnClose}
        onProviderAdded={mockOnProviderAdded}
      />
    );

    await waitFor(() => {
      expect(screen.queryByText('BytePlus')).not.toBeInTheDocument();
    });
  });

  it('includes non-excluded providers in the list', async () => {
    render(
      <AddProviderModal
        isOpen={true}
        onClose={mockOnClose}
        onProviderAdded={mockOnProviderAdded}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('DeepSeek')).toBeInTheDocument();
      expect(screen.getByText('xAI')).toBeInTheDocument();
      expect(screen.getByText('ZAI')).toBeInTheDocument();
    });
  });

  it('shows ADDED badge for already configured providers', async () => {
    render(
      <AddProviderModal
        isOpen={true}
        onClose={mockOnClose}
        onProviderAdded={mockOnProviderAdded}
      />
    );

    await waitFor(() => {
      const addedBadge = screen.getByText('ADDED');
      expect(addedBadge).toBeInTheDocument();
    });
  });

  it('shows model count for each provider', async () => {
    render(
      <AddProviderModal
        isOpen={true}
        onClose={mockOnClose}
        onProviderAdded={mockOnProviderAdded}
      />
    );

    await waitFor(() => {
      expect(screen.getByText(/8 models/)).toBeInTheDocument();
      expect(screen.getByText(/3 models/)).toBeInTheDocument();
      expect(screen.getByText(/15 models/)).toBeInTheDocument();
    });
  });

  it('filters providers by search text', async () => {
    render(
      <AddProviderModal
        isOpen={true}
        onClose={mockOnClose}
        onProviderAdded={mockOnProviderAdded}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('DeepSeek')).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText('Search providers...');
    fireEvent.change(searchInput, { target: { value: 'deep' } });

    await waitFor(() => {
      expect(screen.getByText('DeepSeek')).toBeInTheDocument();
      expect(screen.queryByText('xAI')).not.toBeInTheDocument();
      expect(screen.queryByText('ZAI')).not.toBeInTheDocument();
    });
  });

  it('shows "No providers found" when search has no matches', async () => {
    render(
      <AddProviderModal
        isOpen={true}
        onClose={mockOnClose}
        onProviderAdded={mockOnProviderAdded}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('DeepSeek')).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText('Search providers...');
    fireEvent.change(searchInput, { target: { value: 'nonexistent' } });

    await waitFor(() => {
      expect(screen.getByText('No providers found')).toBeInTheDocument();
    });
  });

  it('transitions to configure step when provider is selected', async () => {
    render(
      <AddProviderModal
        isOpen={true}
        onClose={mockOnClose}
        onProviderAdded={mockOnProviderAdded}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('DeepSeek')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('DeepSeek'));

    await waitFor(() => {
      expect(screen.getByText('Configure DeepSeek')).toBeInTheDocument();
    });
  });

  it('shows back button in configure step', async () => {
    render(
      <AddProviderModal
        isOpen={true}
        onClose={mockOnClose}
        onProviderAdded={mockOnProviderAdded}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('DeepSeek')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('DeepSeek'));

    await waitFor(() => {
      const backButton = screen.getByText('arrow_back');
      expect(backButton).toBeInTheDocument();
    });
  });

  it('returns to browse step when back button is clicked', async () => {
    render(
      <AddProviderModal
        isOpen={true}
        onClose={mockOnClose}
        onProviderAdded={mockOnProviderAdded}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('DeepSeek')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('DeepSeek'));

    await waitFor(() => {
      expect(screen.getByText('Configure DeepSeek')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('arrow_back'));

    await waitFor(() => {
      expect(screen.getByText('Add Provider')).toBeInTheDocument();
    });
  });

  it('shows API key input in configure step', async () => {
    render(
      <AddProviderModal
        isOpen={true}
        onClose={mockOnClose}
        onProviderAdded={mockOnProviderAdded}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('DeepSeek')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('DeepSeek'));

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Paste your API key')).toBeInTheDocument();
    });
  });

  it('shows env var hint for providers with env vars', async () => {
    render(
      <AddProviderModal
        isOpen={true}
        onClose={mockOnClose}
        onProviderAdded={mockOnProviderAdded}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('DeepSeek')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('DeepSeek'));

    await waitFor(() => {
      expect(screen.getByText('DEEPSEEK_API_KEY')).toBeInTheDocument();
    });
  });

  it('calls onClose when close button is clicked', async () => {
    render(
      <AddProviderModal
        isOpen={true}
        onClose={mockOnClose}
        onProviderAdded={mockOnProviderAdded}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Add Provider')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('close'));

    expect(mockOnClose).toHaveBeenCalledTimes(1);
  });

  it('calls onClose when clicking backdrop (outer container)', async () => {
    render(
      <AddProviderModal
        isOpen={true}
        onClose={mockOnClose}
        onProviderAdded={mockOnProviderAdded}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Add Provider')).toBeInTheDocument();
    });

    const outerDiv = document.querySelector('.fixed.inset-0');
    expect(outerDiv).toBeTruthy();
    
    if (outerDiv) {
      fireEvent.click(outerDiv);
    }

    expect(mockOnClose).toHaveBeenCalled();
  });

  it('saves API key when Add Provider is clicked', async () => {
    render(
      <AddProviderModal
        isOpen={true}
        onClose={mockOnClose}
        onProviderAdded={mockOnProviderAdded}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('DeepSeek')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('DeepSeek'));

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Paste your API key')).toBeInTheDocument();
    });

    const apiKeyInput = screen.getByPlaceholderText('Paste your API key');
    fireEvent.change(apiKeyInput, { target: { value: 'test-api-key-123' } });

    fireEvent.click(screen.getByText('Add Provider'));

    await waitFor(() => {
      expect(apiClient.apiPost).toHaveBeenCalledWith('/settings/vault/providers/deepseek', { value: 'test-api-key-123' });
      expect(apiClient.apiPost).toHaveBeenCalledWith('/models/reload');
      expect(mockOnProviderAdded).toHaveBeenCalledWith('deepseek');
      expect(mockOnClose).toHaveBeenCalled();
    });
  });

  it('shows error message when save fails', async () => {
    (apiClient.apiPost as ReturnType<typeof vi.fn>).mockRejectedValueOnce(new Error('Network error'));

    render(
      <AddProviderModal
        isOpen={true}
        onClose={mockOnClose}
        onProviderAdded={mockOnProviderAdded}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('DeepSeek')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('DeepSeek'));

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Paste your API key')).toBeInTheDocument();
    });

    const apiKeyInput = screen.getByPlaceholderText('Paste your API key');
    fireEvent.change(apiKeyInput, { target: { value: 'test-api-key' } });

    fireEvent.click(screen.getByText('Add Provider'));

    await waitFor(() => {
      expect(screen.getByText('Network error')).toBeInTheDocument();
    });
  });

  it('disables Add Provider button when API key is empty', async () => {
    render(
      <AddProviderModal
        isOpen={true}
        onClose={mockOnClose}
        onProviderAdded={mockOnProviderAdded}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('DeepSeek')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('DeepSeek'));

    await waitFor(() => {
      const addButton = screen.getByText('Add Provider');
      expect(addButton).toBeDisabled();
    });
  });

  it('shows saving state during save operation', async () => {
    let resolveSave: (value: unknown) => void;
    (apiClient.apiPost as ReturnType<typeof vi.fn>).mockImplementation(() => new Promise(resolve => { resolveSave = resolve; }));

    render(
      <AddProviderModal
        isOpen={true}
        onClose={mockOnClose}
        onProviderAdded={mockOnProviderAdded}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('DeepSeek')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('DeepSeek'));

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Paste your API key')).toBeInTheDocument();
    });

    const apiKeyInput = screen.getByPlaceholderText('Paste your API key');
    fireEvent.change(apiKeyInput, { target: { value: 'test-key' } });

    fireEvent.click(screen.getByText('Add Provider'));

    await waitFor(() => {
      expect(screen.getByText('Saving...')).toBeInTheDocument();
    });

    resolveSave!(undefined);
  });

  it('shows provider count in footer', async () => {
    render(
      <AddProviderModal
        isOpen={true}
        onClose={mockOnClose}
        onProviderAdded={mockOnProviderAdded}
      />
    );

    await waitFor(() => {
      expect(screen.getByText(/available providers/)).toBeInTheDocument();
    });

    const footer = screen.getByText(/available providers/);
    expect(footer.textContent).toContain('4 available providers');
    expect(footer.textContent).toContain('1 already configured');
  });

  it('sorts providers alphabetically', async () => {
    render(
      <AddProviderModal
        isOpen={true}
        onClose={mockOnClose}
        onProviderAdded={mockOnProviderAdded}
      />
    );

    await waitFor(() => {
      const providerButtons = screen.getAllByRole('button').filter(btn => 
        btn.textContent?.includes('DeepSeek') || 
        btn.textContent?.includes('xAI') || 
        btn.textContent?.includes('ZAI') ||
        btn.textContent?.includes('OpenRouter')
      );

      const providerNames = providerButtons.map(btn => btn.textContent);
      const deepseekIndex = providerNames.findIndex(n => n?.includes('DeepSeek'));
      const openrouterIndex = providerNames.findIndex(n => n?.includes('OpenRouter'));
      const xaiIndex = providerNames.findIndex(n => n?.includes('xAI'));
      const zaiIndex = providerNames.findIndex(n => n?.includes('ZAI'));

      expect(deepseekIndex).toBeLessThan(openrouterIndex);
      expect(openrouterIndex).toBeLessThan(xaiIndex);
      expect(xaiIndex).toBeLessThan(zaiIndex);
    });
  });

  it('cannot select already configured provider', async () => {
    render(
      <AddProviderModal
        isOpen={true}
        onClose={mockOnClose}
        onProviderAdded={mockOnProviderAdded}
      />
    );

    await waitFor(() => {
      const openRouterButton = screen.getByText('OpenRouter').closest('button');
      expect(openRouterButton).toBeDisabled();
    });
  });
});
