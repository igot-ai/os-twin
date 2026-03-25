/**
 * Mock Real-Time Service
 * Simulates real-time updates via an event emitter pattern.
 * Components can subscribe to 'progress' updates.
 */

type RealTimeEvent = 'progress' | 'notification' | 'message';
type Listener = (data: unknown) => void;

class MockRealTimeService {
  private listeners: Map<RealTimeEvent, Set<Listener>> = new Map();
  private interval: NodeJS.Timeout | null = null;
  private enabled: boolean = process.env.NEXT_PUBLIC_ENABLE_MOCK_REALTIME === 'true';

  constructor() {
    if (this.enabled) {
      this.startSimulation();
    }
  }

  subscribe(event: RealTimeEvent, listener: Listener) {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, new Set());
    }
    this.listeners.get(event)?.add(listener);

    return () => {
      this.listeners.get(event)?.delete(listener);
    };
  }

  private emit(event: RealTimeEvent, data: unknown) {
    this.listeners.get(event)?.forEach((listener) => listener(data));
  }

  private startSimulation() {
    this.interval = setInterval(() => {
      // Simulate progress updates for active epics
      const epicRefs = ['EPIC-002', 'EPIC-006'];
      const ref = epicRefs[Math.floor(Math.random() * epicRefs.length)];
      
      this.emit('progress', {
        epic_ref: ref,
        progress: Math.min(100, Math.floor(Math.random() * 5) + 30), // Random increase for demo
        ts: new Date().toISOString(),
      });

      // Occasional random notification
      if (Math.random() > 0.8) {
        this.emit('notification', {
          id: `notif-sim-${Date.now()}`,
          ts: new Date().toISOString(),
          type: 'info',
          title: 'Simulated Update',
          body: 'Background task progress update received.',
          read: false,
        });
      }
    }, 5000); // Every 5 seconds
  }

  stopSimulation() {
    if (this.interval) {
      clearInterval(this.interval);
      this.interval = null;
    }
  }
}

export const mockRealTime = new MockRealTimeService();
