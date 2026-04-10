/**
 * asset-staging.ts — Unified attachment staging buffer.
 *
 * Shared by Discord, Telegram, and conceptually by the web UI.
 * Provides the stage → flush lifecycle:
 *
 *   1. stageAttachments()  — download files from CDN and buffer in session
 *   2. flushStagedAttachments()  — upload buffered files to a plan via API
 *   3. clearStagedAttachments()  — discard buffered files (e.g. on /cancel)
 *
 * Files are downloaded immediately (before CDN URLs expire) and held in
 * session memory until a planId becomes available.
 */

import { getSession, type StagedAttachment } from './sessions';
import api from './api';
import { guessAssetType } from './connectors/utils';

/** Maximum total bytes that can be staged per session (50 MB). */
export const MAX_STAGED_BYTES = 50 * 1024 * 1024;

// ── Types ─────────────────────────────────────────────────────────

export interface AttachmentInput {
  url: string;
  name: string;
  contentType?: string | null;
}

export interface StageResult {
  staged: number;
  failed: number;
  failedNames: string[];
  /** True if the total buffer size would exceed MAX_STAGED_BYTES. */
  rejected: boolean;
}

export interface FlushResult {
  saved: Array<{ filename: string; original_name: string; mime_type?: string; [k: string]: any }>;
  failures: string[];
}

// ── Download helper ───────────────────────────────────────────────

/**
 * Download a single attachment from a URL into a StagedAttachment.
 * Returns null if the download fails.
 */
export async function downloadAttachment(
  input: AttachmentInput,
): Promise<StagedAttachment | null> {
  try {
    const response = await fetch(input.url);
    if (!response.ok) return null;

    const buffer = await response.arrayBuffer();
    const mimeType =
      input.contentType ||
      response.headers.get('content-type') ||
      'application/octet-stream';

    return {
      data: new Uint8Array(buffer),
      name: input.name || 'attachment',
      mimeType,
      stagedAt: Date.now(),
    };
  } catch {
    return null;
  }
}

// ── Stage ─────────────────────────────────────────────────────────

/**
 * Download attachments from their source URLs and buffer them in the
 * user's session. Call this when a message arrives with files but no
 * planId is available yet.
 */
export async function stageAttachments(
  userId: string | number,
  platform: string,
  attachments: AttachmentInput[],
  epicRef?: string,
): Promise<StageResult> {
  const session = getSession(userId, platform);
  if (!session.pendingAttachments) session.pendingAttachments = [];

  const currentSize = getStagedSizeBytes(userId, platform);
  const result: StageResult = { staged: 0, failed: 0, failedNames: [], rejected: false };

  for (const att of attachments) {
    const downloaded = await downloadAttachment(att);
    if (!downloaded) {
      result.failed++;
      result.failedNames.push(att.name);
      continue;
    }

    // Check size limit
    if (currentSize + downloaded.data.byteLength > MAX_STAGED_BYTES) {
      result.rejected = true;
      break;
    }

    if (epicRef) downloaded.epicRef = epicRef;
    session.pendingAttachments.push(downloaded);
    result.staged++;
  }

  return result;
}

// ── Flush ─────────────────────────────────────────────────────────

/**
 * Upload all staged attachments to a plan via the dashboard API,
 * then clear the buffer. Call this after a plan has been created.
 */
export async function flushStagedAttachments(
  userId: string | number,
  platform: string,
  planId: string,
): Promise<FlushResult> {
  const session = getSession(userId, platform);
  const pending = session.pendingAttachments || [];

  if (pending.length === 0) {
    return { saved: [], failures: [] };
  }

  // Determine epic ref (use first file's epicRef if any)
  const epicRef = pending.find((a) => a.epicRef)?.epicRef;
  const firstFile = pending[0];
  const assetType = guessAssetType(firstFile.name, firstFile.mimeType);

  const files = pending.map((a) => ({
    name: a.name,
    contentType: a.mimeType,
    data: a.data,
  }));

  // Always clear the buffer after attempting upload
  session.pendingAttachments = [];

  const uploadResult = await api.uploadPlanAssets(planId, files, {
    epicRef,
    assetType,
  });

  if (uploadResult.error) {
    return { saved: [], failures: [uploadResult.error] };
  }

  return { saved: uploadResult.assets || [], failures: [] };
}

// ── Clear ─────────────────────────────────────────────────────────

/** Discard all staged attachments (e.g. on /cancel). */
export function clearStagedAttachments(
  userId: string | number,
  platform: string,
): void {
  const session = getSession(userId, platform);
  session.pendingAttachments = [];
}

// ── Queries ───────────────────────────────────────────────────────

/** Number of files currently staged for this session. */
export function getStagedCount(
  userId: string | number,
  platform: string,
): number {
  const session = getSession(userId, platform);
  return (session.pendingAttachments || []).length;
}

/** Total bytes currently staged for this session. */
export function getStagedSizeBytes(
  userId: string | number,
  platform: string,
): number {
  const session = getSession(userId, platform);
  return (session.pendingAttachments || []).reduce(
    (sum, a) => sum + (a.data?.byteLength || 0),
    0,
  );
}
