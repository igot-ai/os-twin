export const MAX_IMAGES = 10;
export const MAX_IMAGE_BYTES = 1 * 1024 * 1024; // 1 MB
export const MAX_DIMENSION = 1536;
export const ACCEPTED_TYPES = ['image/jpeg', 'image/png', 'image/gif', 'image/webp'];

export interface ProcessedImage {
  url: string;   // data:image/jpeg;base64,...
  name: string;
  type: string;
  size: number;  // byte length of the data URI
}

function readFileAsDataURL(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as string);
    reader.onerror = () => reject(new Error(`Failed to read ${file.name}`));
    reader.readAsDataURL(file);
  });
}

function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error('Failed to load image'));
    img.src = src;
  });
}

export async function processImage(file: File): Promise<ProcessedImage> {
  if (!ACCEPTED_TYPES.includes(file.type)) {
    throw new Error(`Unsupported type: ${file.type}. Use JPEG, PNG, GIF, or WebP.`);
  }

  const dataUrl = await readFileAsDataURL(file);
  const img = await loadImage(dataUrl);

  let { width, height } = img;

  // Scale down if exceeds max dimension
  if (width > MAX_DIMENSION || height > MAX_DIMENSION) {
    const scale = MAX_DIMENSION / Math.max(width, height);
    width = Math.round(width * scale);
    height = Math.round(height * scale);
  }

  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext('2d')!;
  ctx.drawImage(img, 0, 0, width, height);

  // Try quality 0.8 first, then 0.6 if too large
  let result = canvas.toDataURL('image/jpeg', 0.8);
  if (result.length > MAX_IMAGE_BYTES) {
    result = canvas.toDataURL('image/jpeg', 0.6);
  }
  if (result.length > MAX_IMAGE_BYTES) {
    throw new Error(`${file.name} is too large even after compression (${(result.length / 1024 / 1024).toFixed(1)}MB).`);
  }

  return {
    url: result,
    name: file.name,
    type: 'image/jpeg',
    size: result.length,
  };
}

export async function processImages(
  files: FileList | File[]
): Promise<{ images: ProcessedImage[]; errors: string[] }> {
  const images: ProcessedImage[] = [];
  const errors: string[] = [];
  const fileArray = Array.from(files).slice(0, MAX_IMAGES);

  if (Array.from(files).length > MAX_IMAGES) {
    errors.push(`Only ${MAX_IMAGES} images allowed. Extra files ignored.`);
  }

  for (const file of fileArray) {
    try {
      images.push(await processImage(file));
    } catch (e: any) {
      errors.push(e.message || `Failed to process ${file.name}`);
    }
  }

  return { images, errors };
}
