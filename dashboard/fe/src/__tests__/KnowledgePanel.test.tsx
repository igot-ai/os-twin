/**
 * Unit tests for KnowledgePanel.
 *
 * Verifies that the Knowledge settings panel:
 * - Renders the LLM, embedding, and dimension sections.
 * - Reflects the current effective values from props.
 * - Calls onUpdate when the LLM dropdown changes.
 * - Calls onUpdate when the embedding input is committed (blur / Enter).
 * - Picks up the embedding dimension when a suggested model is selected.
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';

import { KnowledgePanel } from '../components/settings/KnowledgePanel';
import type { KnowledgeSettings, ModelInfo } from '../types/settings';

const mockModels: ModelInfo[] = [
  { id: 'anthropic/claude-haiku-4-5', label: 'Claude Haiku 4.5', provider_id: 'anthropic' },
  { id: 'openai/gpt-5',               label: 'GPT-5',            provider_id: 'openai' },
  // embedding model — should be filtered out of the chat picker
  { id: 'openai/text-embedding-3-small', label: 'OpenAI Embedding', provider_id: 'openai' },
];

const defaults: KnowledgeSettings = {
  llm_model: '',
  embedding_model: '',
  embedding_dimension: 384,
};

describe('KnowledgePanel', () => {
  it('renders LLM, embedding, and dimension sections', () => {
    const onUpdate = vi.fn();
    render(<KnowledgePanel knowledge={defaults} onUpdate={onUpdate} allModels={mockModels} />);

    expect(screen.getByText(/Knowledge Models/i)).toBeInTheDocument();
    expect(screen.getByText(/^LLM Model$/i)).toBeInTheDocument();
    expect(screen.getByText(/^Embedding Model$/i)).toBeInTheDocument();
    expect(screen.getByText(/^Embedding Dimension$/i)).toBeInTheDocument();
  });

  it('shows the current LLM model selected in the dropdown', () => {
    const onUpdate = vi.fn();
    render(
      <KnowledgePanel
        knowledge={{ ...defaults, llm_model: 'anthropic/claude-haiku-4-5' }}
        onUpdate={onUpdate}
        allModels={mockModels}
      />,
    );
    const select = screen.getByRole('combobox') as HTMLSelectElement;
    expect(select.value).toBe('anthropic/claude-haiku-4-5');
  });

  it('filters out embedding models from the chat-model dropdown', () => {
    const onUpdate = vi.fn();
    render(<KnowledgePanel knowledge={defaults} onUpdate={onUpdate} allModels={mockModels} />);
    const select = screen.getByRole('combobox') as HTMLSelectElement;
    const optionTexts = Array.from(select.options).map((o) => o.value);
    expect(optionTexts).toContain('anthropic/claude-haiku-4-5');
    expect(optionTexts).toContain('openai/gpt-5');
    expect(optionTexts).not.toContain('openai/text-embedding-3-small');
  });

  it('falls back to the "server default" option when no LLM is set', () => {
    const onUpdate = vi.fn();
    render(<KnowledgePanel knowledge={defaults} onUpdate={onUpdate} allModels={mockModels} />);
    const select = screen.getByRole('combobox') as HTMLSelectElement;
    expect(select.value).toBe('');
    // Both an <option> and a "Currently effective" line render with this phrase
    expect(screen.getAllByText(/server default/i).length).toBeGreaterThanOrEqual(1);
  });

  it('calls onUpdate when the LLM dropdown is changed', async () => {
    const onUpdate = vi.fn().mockResolvedValue(undefined);
    render(<KnowledgePanel knowledge={defaults} onUpdate={onUpdate} allModels={mockModels} />);
    const select = screen.getByRole('combobox');
    fireEvent.change(select, { target: { value: 'openai/gpt-5' } });
    expect(onUpdate).toHaveBeenCalledWith({ llm_model: 'openai/gpt-5' });
  });

  it('calls onUpdate with model + dimension when a suggested embedding is clicked', async () => {
    const onUpdate = vi.fn().mockResolvedValue(undefined);
    render(<KnowledgePanel knowledge={defaults} onUpdate={onUpdate} allModels={mockModels} />);

    // Click the suggestion button for bge-base-en-v1.5 (dim 768)
    const button = screen.getByRole('button', { name: /BAAI\/bge-base-en-v1\.5/ });
    fireEvent.click(button);

    expect(onUpdate).toHaveBeenCalledWith({
      embedding_model: 'BAAI/bge-base-en-v1.5',
      embedding_dimension: 768,
    });
  });

  it('calls onUpdate when the embedding input is changed and blurred with a custom id', () => {
    const onUpdate = vi.fn().mockResolvedValue(undefined);
    render(<KnowledgePanel knowledge={defaults} onUpdate={onUpdate} allModels={mockModels} />);
    const input = screen.getByPlaceholderText(/BAAI\/bge-small-en-v1\.5/);
    fireEvent.change(input, { target: { value: 'custom/model-id' } });
    fireEvent.blur(input);
    expect(onUpdate).toHaveBeenCalledWith({
      embedding_model: 'custom/model-id',
      // unknown to suggestion list → preserves the prior dimension
      embedding_dimension: 384,
    });
  });

  it('does not call onUpdate when the embedding value is unchanged on blur', () => {
    const onUpdate = vi.fn();
    render(
      <KnowledgePanel
        knowledge={{ ...defaults, embedding_model: 'BAAI/bge-small-en-v1.5' }}
        onUpdate={onUpdate}
        allModels={mockModels}
      />,
    );
    const input = screen.getByPlaceholderText(/BAAI\/bge-small-en-v1\.5/);
    fireEvent.blur(input);
    expect(onUpdate).not.toHaveBeenCalled();
  });

  it('shows the read-only embedding dimension', () => {
    const onUpdate = vi.fn();
    render(
      <KnowledgePanel
        knowledge={{ ...defaults, embedding_dimension: 768 }}
        onUpdate={onUpdate}
        allModels={mockModels}
      />,
    );
    expect(screen.getByText('768')).toBeInTheDocument();
    expect(screen.getByText(/dimensions/i)).toBeInTheDocument();
  });

  it('still shows the "server default" option when no providers are configured', () => {
    const onUpdate = vi.fn();
    render(<KnowledgePanel knowledge={defaults} onUpdate={onUpdate} allModels={[]} />);
    const select = screen.getByRole('combobox') as HTMLSelectElement;
    // the default option is always present so the user is not blocked
    expect(Array.from(select.options).some((o) => /server default/i.test(o.text))).toBe(true);
  });
});
