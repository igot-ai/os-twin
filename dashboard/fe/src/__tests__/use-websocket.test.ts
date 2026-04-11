import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useWebSocket } from '../hooks/use-websocket';

// Mock WebSocket
class MockWebSocket {
  static OPEN = 1;
  static CLOSED = 3;
  static CONNECTING = 0;

  url: string;
  readyState: number = MockWebSocket.CONNECTING;
  onopen: ((ev: any) => void) | null = null;
  onclose: ((ev: any) => void) | null = null;
  onmessage: ((ev: any) => void) | null = null;
  onerror: ((ev: any) => void) | null = null;
  sent: string[] = [];

  constructor(url: string) {
    this.url = url;
    // Simulate async connection
    setTimeout(() => {
      this.readyState = MockWebSocket.OPEN;
      this.onopen?.({});
    }, 0);
  }

  send(data: string) {
    this.sent.push(data);
  }

  close() {
    this.readyState = MockWebSocket.CLOSED;
    this.onclose?.({});
  }
}

describe('use-websocket hook', () => {
  let originalWebSocket: typeof WebSocket;

  beforeEach(() => {
    originalWebSocket = globalThis.WebSocket;
    (globalThis as any).WebSocket = MockWebSocket;
    vi.useFakeTimers();
  });

  afterEach(() => {
    globalThis.WebSocket = originalWebSocket;
    vi.useRealTimers();
  });

  it('should start disconnected', () => {
    const { result } = renderHook(() => useWebSocket('ws://localhost:8080'));
    expect(result.current.isConnected).toBe(false);
    expect(result.current.lastMessage).toBeNull();
  });

  it('should not connect when url is null', () => {
    const { result } = renderHook(() => useWebSocket(null));
    expect(result.current.isConnected).toBe(false);
  });

  it('should connect and set isConnected to true', async () => {
    const { result } = renderHook(() => useWebSocket('ws://localhost:8080'));

    // Advance timers to trigger the async onopen
    await act(async () => {
      vi.advanceTimersByTime(10);
    });

    expect(result.current.isConnected).toBe(true);
  });

  it('should handle incoming messages', async () => {
    let wsInstance: MockWebSocket | null = null;
    const OrigMock = MockWebSocket;
    (globalThis as any).WebSocket = class extends OrigMock {
      constructor(url: string) {
        super(url);
        wsInstance = this;
      }
    };

    const { result } = renderHook(() => useWebSocket('ws://localhost:8080'));

    await act(async () => {
      vi.advanceTimersByTime(10);
    });

    // Simulate receiving a message
    act(() => {
      wsInstance?.onmessage?.({ data: JSON.stringify({ type: 'update', value: 42 }) });
    });

    expect(result.current.lastMessage).toEqual({ type: 'update', value: 42 });
  });

  it('should set isConnected to false on close', async () => {
    let wsInstance: MockWebSocket | null = null;
    const OrigMock = MockWebSocket;
    (globalThis as any).WebSocket = class extends OrigMock {
      constructor(url: string) {
        super(url);
        wsInstance = this;
      }
    };

    const { result } = renderHook(() => useWebSocket('ws://localhost:8080'));

    await act(async () => {
      vi.advanceTimersByTime(10);
    });

    expect(result.current.isConnected).toBe(true);

    act(() => {
      wsInstance?.close();
    });

    expect(result.current.isConnected).toBe(false);
  });

  it('should expose a sendMessage function', async () => {
    const { result } = renderHook(() => useWebSocket('ws://localhost:8080'));
    expect(typeof result.current.sendMessage).toBe('function');
  });

  it('should disconnect on unmount', async () => {
    let wsInstance: MockWebSocket | null = null;
    const OrigMock = MockWebSocket;
    (globalThis as any).WebSocket = class extends OrigMock {
      constructor(url: string) {
        super(url);
        wsInstance = this;
      }
    };

    const { unmount } = renderHook(() => useWebSocket('ws://localhost:8080'));

    await act(async () => {
      vi.advanceTimersByTime(10);
    });

    unmount();
    expect((wsInstance as any)?.readyState).toBe(MockWebSocket.CLOSED);
  });
});
