/**
 * Decode a base64-encoded string into a Uint8Array.
 * Shared utility used by PdfViewer, DocxViewer, and ExcelViewer.
 * 
 * SECURITY (P3-23): Validates base64 length to prevent memory exhaustion.
 * Base64 encoding expands data by ~33%, so a 2MB base64 string decodes to ~1.5MB.
 * We cap at 3MB base64 input as a safety limit.
 */
const MAX_BASE64_LENGTH = 3 * 1024 * 1024; // 3MB base64 input limit

export function base64ToUint8Array(base64: string): Uint8Array {
  if (base64.length > MAX_BASE64_LENGTH) {
    throw new Error(`Base64 data exceeds maximum size limit (${MAX_BASE64_LENGTH / 1024 / 1024}MB)`);
  }
  const byteChars = atob(base64);
  const byteArray = new Uint8Array(byteChars.length);
  for (let i = 0; i < byteChars.length; i++) {
    byteArray[i] = byteChars.charCodeAt(i);
  }
  return byteArray;
}
