import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MAX_IMAGES, MAX_IMAGE_BYTES, MAX_DIMENSION, ACCEPTED_TYPES, processImage, processImages } from '../lib/image-utils';

// Mock DOM APIs that don't exist in jsdom/node
const mockCanvasContext = {
  drawImage: vi.fn(),
};

const mockCanvas = {
  width: 0,
  height: 0,
  getContext: vi.fn(() => mockCanvasContext),
  toDataURL: vi.fn(() => 'data:image/jpeg;base64,mockdata'),
};

beforeEach(() => {
  vi.clearAllMocks();

  // Mock document.createElement for 'canvas'
  vi.spyOn(document, 'createElement').mockImplementation((tag: string) => {
    if (tag === 'canvas') return mockCanvas as any;
    return document.createElement(tag);
  });
});

// Helper to create a mock File
function createMockFile(name: string, type: string, size = 1000): File {
  const content = new ArrayBuffer(size);
  return new File([content], name, { type });
}

describe('image-utils constants', () => {
  it('MAX_IMAGES should be 10', () => {
    expect(MAX_IMAGES).toBe(10);
  });

  it('MAX_IMAGE_BYTES should be 1MB', () => {
    expect(MAX_IMAGE_BYTES).toBe(1 * 1024 * 1024);
  });

  it('MAX_DIMENSION should be 1536', () => {
    expect(MAX_DIMENSION).toBe(1536);
  });

  it('ACCEPTED_TYPES should include jpeg, png, gif, webp', () => {
    expect(ACCEPTED_TYPES).toContain('image/jpeg');
    expect(ACCEPTED_TYPES).toContain('image/png');
    expect(ACCEPTED_TYPES).toContain('image/gif');
    expect(ACCEPTED_TYPES).toContain('image/webp');
  });

  it('ACCEPTED_TYPES should not include svg or bmp', () => {
    expect(ACCEPTED_TYPES).not.toContain('image/svg+xml');
    expect(ACCEPTED_TYPES).not.toContain('image/bmp');
  });
});

describe('processImage', () => {
  it('should reject unsupported file types', async () => {
    const file = createMockFile('test.pdf', 'application/pdf');
    await expect(processImage(file)).rejects.toThrow('Unsupported type: application/pdf');
  });

  it('should reject text files', async () => {
    const file = createMockFile('test.txt', 'text/plain');
    await expect(processImage(file)).rejects.toThrow('Unsupported type: text/plain');
  });

  it('should reject svg files', async () => {
    const file = createMockFile('icon.svg', 'image/svg+xml');
    await expect(processImage(file)).rejects.toThrow('Unsupported type: image/svg+xml');
  });
});

describe('processImages', () => {
  it('should return empty arrays for empty input', async () => {
    const result = await processImages([]);
    expect(result.images).toEqual([]);
    expect(result.errors).toEqual([]);
  });

  it('should add error when files exceed MAX_IMAGES', async () => {
    // Create more than MAX_IMAGES files
    const files: File[] = [];
    for (let i = 0; i < MAX_IMAGES + 3; i++) {
      files.push(createMockFile(`img${i}.pdf`, 'application/pdf')); // will fail individually too
    }

    const result = await processImages(files);
    // Should have the "Only N images allowed" error
    expect(result.errors.some(e => e.includes(`Only ${MAX_IMAGES} images allowed`))).toBe(true);
  });

  it('should collect individual processing errors', async () => {
    const files = [
      createMockFile('doc.pdf', 'application/pdf'),
      createMockFile('text.txt', 'text/plain'),
    ];

    const result = await processImages(files);
    // Both should fail validation
    expect(result.errors.length).toBe(2);
    expect(result.images).toEqual([]);
  });
});
