import '@testing-library/jest-dom';

global.ResizeObserver = class ResizeObserver {
  private callback: ResizeObserverCallback;
  constructor(callback: ResizeObserverCallback) {
    this.callback = callback;
  }
  observe() {}
  unobserve() {}
  disconnect() {}
};

// Minimal DOMMatrix polyfill for jsdom (required by react-pdf/pdfjs-dist at import time).
// Only stubs geometry operations — not suitable for tests that assert on matrix math.
global.DOMMatrix = class DOMMatrix {
  a = 1; b = 0; c = 0; d = 1; e = 0; f = 0;
  is2D = true; isIdentity = true;
  static fromMatrix() { return new DOMMatrix(); }
  static fromFloat32Array() { return new DOMMatrix(); }
  static fromFloat64Array() { return new DOMMatrix(); }
  multiply() { return new DOMMatrix(); }
  inverse() { return new DOMMatrix(); }
  translate() { return new DOMMatrix(); }
  scale() { return new DOMMatrix(); }
  rotate() { return new DOMMatrix(); }
  rotateFromVector() { return new DOMMatrix(); }
  skewX() { return new DOMMatrix(); }
  skewY() { return new DOMMatrix(); }
  flipX() { return new DOMMatrix(); }
  flipY() { return new DOMMatrix(); }
  setMatrixValue() { return this; }
  toString() { return 'matrix(1, 0, 0, 1, 0, 0)'; }
  toJSON() { return { a: 1, b: 0, c: 0, d: 1, e: 0, f: 0 }; }
} as any;
