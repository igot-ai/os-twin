import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach, beforeAll } from 'vitest';
import '@testing-library/jest-dom';
import { ModelSelect } from '../components/settings/ModelSelect';
import type { ModelInfo } from '../types/settings';

beforeAll(() => {
  Element.prototype.scrollIntoView = vi.fn();
});

const mockModels: ModelInfo[] = [
  { id: 'anthropic/claude-opus-4', label: 'Claude Opus 4', provider_id: 'anthropic', context_window: '200k', tier: 'flagship' },
  { id: 'anthropic/claude-sonnet-4', label: 'Claude Sonnet 4', provider_id: 'anthropic', context_window: '200k', tier: 'balanced' },
  { id: 'openai/gpt-5', label: 'GPT-5', provider_id: 'openai', context_window: '128k', tier: 'flagship' },
  { id: 'google/gemini-3-flash', label: 'Gemini 3 Flash', provider_id: 'google', context_window: '1M', tier: 'fast' },
];

const mockProviders = {
  anthropic: { name: 'Anthropic', logo_url: 'https://models.dev/logos/anthropic.svg' },
  openai: { name: 'OpenAI', logo_url: 'https://models.dev/logos/openai.svg' },
  google: { name: 'Google', logo_url: 'https://models.dev/logos/google.svg' },
};

describe('ModelSelect', () => {
  const mockOnChange = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('T-002.3: Searchable Combobox', () => {
    it('renders a button trigger (not a legacy <select>)', () => {
      render(
        <ModelSelect
          value=""
          onChange={mockOnChange}
          models={mockModels}
          placeholder="Select model"
        />
      );

      const trigger = screen.getByRole('button', { name: /select model/i });
      expect(trigger).toBeInTheDocument();
      expect(trigger.tagName).toBe('BUTTON');
    });

    it('opens a searchable dropdown when clicked', () => {
      render(
        <ModelSelect
          value=""
          onChange={mockOnChange}
          models={mockModels}
          placeholder="Select model"
        />
      );

      fireEvent.click(screen.getByRole('button', { name: /select model/i }));

      expect(screen.getByPlaceholderText(/search models/i)).toBeInTheDocument();
    });

    it('filters models by search query', async () => {
      render(
        <ModelSelect
          value=""
          onChange={mockOnChange}
          models={mockModels}
          placeholder="Select model"
        />
      );

      fireEvent.click(screen.getByRole('button', { name: /select model/i }));

      const searchInput = screen.getByPlaceholderText(/search models/i);
      fireEvent.change(searchInput, { target: { value: 'claude' } });

      await waitFor(() => {
        expect(screen.getByText(/Claude Opus 4/)).toBeInTheDocument();
        expect(screen.getByText(/Claude Sonnet 4/)).toBeInTheDocument();
        expect(screen.queryByText(/GPT-5/)).not.toBeInTheDocument();
      });
    });

    it('filters models by provider name', async () => {
      render(
        <ModelSelect
          value=""
          onChange={mockOnChange}
          models={mockModels}
          providers={mockProviders}
          placeholder="Select model"
        />
      );

      fireEvent.click(screen.getByRole('button', { name: /select model/i }));

      const searchInput = screen.getByPlaceholderText(/search models/i);
      fireEvent.change(searchInput, { target: { value: 'openai' } });

      await waitFor(() => {
        expect(screen.getByText(/GPT-5/)).toBeInTheDocument();
        expect(screen.queryByText(/Claude/)).not.toBeInTheDocument();
      });
    });

    it('shows "No models match" when search has no results', async () => {
      render(
        <ModelSelect
          value=""
          onChange={mockOnChange}
          models={mockModels}
          placeholder="Select model"
        />
      );

      fireEvent.click(screen.getByRole('button', { name: /select model/i }));

      const searchInput = screen.getByPlaceholderText(/search models/i);
      fireEvent.change(searchInput, { target: { value: 'nonexistent-model-xyz' } });

      await waitFor(() => {
        expect(screen.getByText(/no models match/i)).toBeInTheDocument();
      });
    });

    it('clears search with X button', async () => {
      render(
        <ModelSelect
          value=""
          onChange={mockOnChange}
          models={mockModels}
          placeholder="Select model"
        />
      );

      fireEvent.click(screen.getByRole('button', { name: /select model/i }));

      const searchInput = screen.getByPlaceholderText(/search models/i);
      fireEvent.change(searchInput, { target: { value: 'claude' } });

      await waitFor(() => {
        expect(screen.getByText(/Claude Opus 4/)).toBeInTheDocument();
      });

      const closeButton = screen.getByRole('button', { name: 'close' });
      fireEvent.click(closeButton);

      await waitFor(() => {
        expect(searchInput).toHaveValue('');
      });
    });
  });

  describe('Selection', () => {
    it('calls onChange when a model is selected', async () => {
      render(
        <ModelSelect
          value=""
          onChange={mockOnChange}
          models={mockModels}
          placeholder="Select model"
        />
      );

      fireEvent.click(screen.getByRole('button', { name: /select model/i }));

      const option = screen.getByRole('button', { name: /Claude Opus 4/ });
      fireEvent.click(option);

      expect(mockOnChange).toHaveBeenCalledWith('anthropic/claude-opus-4');
    });

    it('displays selected model in the trigger', () => {
      render(
        <ModelSelect
          value="anthropic/claude-opus-4"
          onChange={mockOnChange}
          models={mockModels}
          placeholder="Select model"
        />
      );

      expect(screen.getByText(/Claude Opus 4/)).toBeInTheDocument();
    });

    it('shows checkmark on selected model in dropdown', () => {
      render(
        <ModelSelect
          value="anthropic/claude-opus-4"
          onChange={mockOnChange}
          models={mockModels}
          placeholder="Select model"
        />
      );

      const triggers = screen.getAllByRole('button').filter((b) =>
        b.textContent?.includes('Claude Opus 4')
      );
      fireEvent.click(triggers[0]);

      const checkIcons = screen.getAllByText('check');
      expect(checkIcons.length).toBeGreaterThan(0);
    });
  });

  describe('Keyboard Navigation', () => {
    it('opens dropdown with ArrowDown key', () => {
      render(
        <ModelSelect
          value=""
          onChange={mockOnChange}
          models={mockModels}
          placeholder="Select model"
        />
      );

      const trigger = screen.getByRole('button', { name: /select model/i });
      fireEvent.keyDown(trigger, { key: 'ArrowDown' });

      expect(screen.getByPlaceholderText(/search models/i)).toBeInTheDocument();
    });

    it('opens dropdown with Enter key', () => {
      render(
        <ModelSelect
          value=""
          onChange={mockOnChange}
          models={mockModels}
          placeholder="Select model"
        />
      );

      const trigger = screen.getByRole('button', { name: /select model/i });
      fireEvent.keyDown(trigger, { key: 'Enter' });

      expect(screen.getByPlaceholderText(/search models/i)).toBeInTheDocument();
    });

    it('closes dropdown with Escape key', () => {
      render(
        <ModelSelect
          value=""
          onChange={mockOnChange}
          models={mockModels}
          placeholder="Select model"
        />
      );

      const trigger = screen.getByRole('button', { name: /select model/i });
      fireEvent.click(trigger);
      expect(screen.getByPlaceholderText(/search models/i)).toBeInTheDocument();

      fireEvent.keyDown(trigger, { key: 'Escape' });

      expect(screen.queryByPlaceholderText(/search models/i)).not.toBeInTheDocument();
    });

    it('navigates with ArrowUp/ArrowDown', async () => {
      render(
        <ModelSelect
          value=""
          onChange={mockOnChange}
          models={mockModels}
          placeholder="Select model"
        />
      );

      const trigger = screen.getByRole('button', { name: /select model/i });
      fireEvent.click(trigger);

      fireEvent.keyDown(trigger, { key: 'ArrowDown' });
      fireEvent.keyDown(trigger, { key: 'ArrowDown' });
      fireEvent.keyDown(trigger, { key: 'ArrowUp' });
    });

    it('selects highlighted item with Enter', async () => {
      render(
        <ModelSelect
          value=""
          onChange={mockOnChange}
          models={mockModels}
          placeholder="Select model"
        />
      );

      const trigger = screen.getByRole('button', { name: /select model/i });
      fireEvent.click(trigger);

      fireEvent.keyDown(trigger, { key: 'ArrowDown' });
      fireEvent.keyDown(trigger, { key: 'Enter' });

      expect(mockOnChange).toHaveBeenCalled();
    });
  });

  describe('Grouping by Provider', () => {
    it('groups models by provider_id', async () => {
      render(
        <ModelSelect
          value=""
          onChange={mockOnChange}
          models={mockModels}
          providers={mockProviders}
          placeholder="Select model"
        />
      );

      fireEvent.click(screen.getByRole('button', { name: /select model/i }));

      expect(screen.getByText('Anthropic')).toBeInTheDocument();
      expect(screen.getByText('OpenAI')).toBeInTheDocument();
      expect(screen.getByText('Google')).toBeInTheDocument();
    });

    it('shows model count per provider', async () => {
      render(
        <ModelSelect
          value=""
          onChange={mockOnChange}
          models={mockModels}
          providers={mockProviders}
          placeholder="Select model"
        />
      );

      fireEvent.click(screen.getByRole('button', { name: /select model/i }));

      expect(screen.getByText('2')).toBeInTheDocument();
    });
  });

  describe('Display Options', () => {
    it('shows tier badges when showTier is true', () => {
      render(
        <ModelSelect
          value=""
          onChange={mockOnChange}
          models={mockModels}
          showTier={true}
          placeholder="Select model"
        />
      );

      fireEvent.click(screen.getByRole('button', { name: /select model/i }));

      expect(screen.getAllByText('flagship').length).toBeGreaterThan(0);
      expect(screen.getAllByText('balanced').length).toBeGreaterThan(0);
      expect(screen.getAllByText('fast').length).toBeGreaterThan(0);
    });

    it('hides tier badges when showTier is false', () => {
      render(
        <ModelSelect
          value=""
          onChange={mockOnChange}
          models={mockModels}
          showTier={false}
          placeholder="Select model"
        />
      );

      fireEvent.click(screen.getByRole('button', { name: /select model/i }));

      expect(screen.queryByText('flagship')).not.toBeInTheDocument();
    });

    it('shows context window when showContext is true', () => {
      render(
        <ModelSelect
          value=""
          onChange={mockOnChange}
          models={mockModels}
          showContext={true}
          placeholder="Select model"
        />
      );

      fireEvent.click(screen.getByRole('button', { name: /select model/i }));

      expect(screen.getAllByText('200k').length).toBeGreaterThan(0);
      expect(screen.getByText('128k')).toBeInTheDocument();
    });

    it('hides context window when showContext is false', () => {
      render(
        <ModelSelect
          value=""
          onChange={mockOnChange}
          models={mockModels}
          showContext={false}
          placeholder="Select model"
        />
      );

      fireEvent.click(screen.getByRole('button', { name: /select model/i }));

      expect(screen.queryByText('200k')).not.toBeInTheDocument();
    });
  });

  describe('Disabled State', () => {
    it('does not open dropdown when disabled', () => {
      render(
        <ModelSelect
          value=""
          onChange={mockOnChange}
          models={mockModels}
          disabled={true}
          placeholder="Select model"
        />
      );

      const trigger = screen.getByRole('button', { name: /select model/i });
      fireEvent.click(trigger);

      expect(screen.queryByPlaceholderText(/search models/i)).not.toBeInTheDocument();
    });
  });
});
