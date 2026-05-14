import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import '@testing-library/jest-dom';

import { RuntimePanel } from '../components/settings/RuntimePanel';

describe('RuntimePanel', () => {
  it('updates the canonical poll_interval_seconds field', () => {
    const onUpdate = vi.fn();

    render(
      <RuntimePanel
        runtime={{
          poll_interval_seconds: 5,
          max_concurrent_rooms: 10,
          max_engineer_retries: 3,
          state_timeout_seconds: 900,
          auto_approve_tools: false,
          dynamic_pipelines: true,
          master_agent_model: '',
        }}
        onUpdate={onUpdate}
        allModels={[]}
      />
    );

    const pollSlider = screen.getAllByRole('slider')[0];
    fireEvent.change(pollSlider, { target: { value: '12' } });
    fireEvent.mouseUp(pollSlider);

    expect(onUpdate).toHaveBeenCalledWith({ poll_interval_seconds: 12 });
  });
});
