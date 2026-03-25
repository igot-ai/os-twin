/**
 * API Utils for Mock Routes
 */

import { NextResponse } from 'next/server';

/**
 * Simulates random network latency between 100ms and 300ms.
 */
export async function simulateLatency() {
  const delay = Math.floor(Math.random() * 200) + 100;
  await new Promise((resolve) => setTimeout(resolve, delay));
}

/**
 * Standard success response.
 */
export function successResponse(data: unknown) {
  return NextResponse.json(data);
}

/**
 * Standard error response.
 */
export function errorResponse(message: string, status: number = 400) {
  return NextResponse.json({ message }, { status });
}
