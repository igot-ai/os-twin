import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { CommandPrompt } from './CommandPrompt';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import '@testing-library/jest-dom';

describe('CommandPrompt keyboard behavior', () => {
  beforeEach(() => {
    // jsdom does not implement these, but the auto-resize effect reads them.
    Object.defineProperty(window, 'innerHeight', { value: 800, configurable: true });
  });

  const renderWith = (initial = 'Fill in {{placeholder}}') => {
    const onSubmit = vi.fn();
    const onChange = vi.fn();
    render(
      <CommandPrompt
        value={initial}
        onChange={onChange}
        onSubmit={onSubmit}
      />,
    );
    const textarea = screen.getByRole('textbox', { name: /prompt/i }) as HTMLTextAreaElement;
    return { textarea, onSubmit, onChange };
  };

  it('does NOT submit on plain Enter so multi-line template editing stays safe', () => {
    const { textarea, onSubmit } = renderWith();
    // A plain Enter should fall through to the native textarea — no submit.
    fireEvent.keyDown(textarea, { key: 'Enter' });
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it('does NOT submit on Shift+Enter', () => {
    const { textarea, onSubmit } = renderWith();
    fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: true });
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it('submits on Ctrl+Enter', () => {
    const { textarea, onSubmit } = renderWith('Ship it');
    fireEvent.keyDown(textarea, { key: 'Enter', ctrlKey: true });
    expect(onSubmit).toHaveBeenCalledTimes(1);
    expect(onSubmit).toHaveBeenCalledWith('Ship it', undefined);
  });

  it('submits on Cmd+Enter (macOS)', () => {
    const { textarea, onSubmit } = renderWith('Ship it');
    fireEvent.keyDown(textarea, { key: 'Enter', metaKey: true });
    expect(onSubmit).toHaveBeenCalledTimes(1);
    expect(onSubmit).toHaveBeenCalledWith('Ship it', undefined);
  });

  it('does not submit an empty prompt on Ctrl+Enter', () => {
    const { textarea, onSubmit } = renderWith('   ');
    fireEvent.keyDown(textarea, { key: 'Enter', ctrlKey: true });
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it('exposes a visible hint describing the submit shortcut', () => {
    renderWith();
    const hint = document.getElementById('command-prompt-hint');
    expect(hint).not.toBeNull();
    expect(hint).toHaveTextContent(/ctrl/i);
    expect(hint).toHaveTextContent(/enter/i);
    expect(hint).toHaveTextContent(/new line/i);
  });
});
