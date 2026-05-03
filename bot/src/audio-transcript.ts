/**
 * audio-transcript.ts — Transcribe voice recordings via shared AI gateway.
 *
 * Converts PCM recordings (48kHz, 16-bit, stereo) from Discord voice channels
 * to WAV (16kHz, mono), sends to the AI gateway for transcription.
 */

import fs from 'fs';
import path from 'path';
import config from './config';
import api from './api';
import { complete } from './ai-gateway';

const RECORDINGS_DIR = path.resolve(__dirname, '../recordings');

// PCM format from Discord voice recordings (prism-media opus decoder output)
const PCM_SAMPLE_RATE = 48000;
const PCM_CHANNELS = 2;
const PCM_BIT_DEPTH = 16;

// Target format for transcription (smaller, speech-optimized)
const TARGET_SAMPLE_RATE = 16000;
const TARGET_CHANNELS = 1;

export interface TranscriptionResult {
  text: string;
  filename: string;
  durationSecs: number;
}

/**
 * List available .pcm recordings, newest first.
 */
export function listRecordings(): string[] {
  if (!fs.existsSync(RECORDINGS_DIR)) return [];
  return fs.readdirSync(RECORDINGS_DIR)
    .filter(f => f.endsWith('.pcm'))
    .sort((a, b) => {
      const aTime = fs.statSync(path.join(RECORDINGS_DIR, a)).mtimeMs;
      const bTime = fs.statSync(path.join(RECORDINGS_DIR, b)).mtimeMs;
      return bTime - aTime;
    });
}

/**
 * Convert raw PCM (48kHz, 16-bit, stereo) to WAV (16kHz, 16-bit, mono).
 * Downsamples by averaging stereo channels and picking every 3rd frame.
 */
export function pcmToWav(pcmData: Buffer): Buffer {
  const bytesPerSample = PCM_BIT_DEPTH / 8;
  const frameSize = PCM_CHANNELS * bytesPerSample;
  const totalFrames = Math.floor(pcmData.length / frameSize);
  const downsampleRatio = PCM_SAMPLE_RATE / TARGET_SAMPLE_RATE;

  const outputFrames = Math.floor(totalFrames / downsampleRatio);
  const outputBytesPerFrame = TARGET_CHANNELS * bytesPerSample;
  const dataSize = outputFrames * outputBytesPerFrame;

  // WAV header (44 bytes)
  const header = Buffer.alloc(44);
  header.write('RIFF', 0);
  header.writeUInt32LE(36 + dataSize, 4);
  header.write('WAVE', 8);
  header.write('fmt ', 12);
  header.writeUInt32LE(16, 16);
  header.writeUInt16LE(1, 20);  // PCM format
  header.writeUInt16LE(TARGET_CHANNELS, 22);
  header.writeUInt32LE(TARGET_SAMPLE_RATE, 24);
  header.writeUInt32LE(TARGET_SAMPLE_RATE * TARGET_CHANNELS * bytesPerSample, 28);
  header.writeUInt16LE(TARGET_CHANNELS * bytesPerSample, 32);
  header.writeUInt16LE(PCM_BIT_DEPTH, 34);
  header.write('data', 36);
  header.writeUInt32LE(dataSize, 40);

  // Downsample stereo → mono, 48kHz → 16kHz
  const output = Buffer.alloc(dataSize);
  for (let i = 0; i < outputFrames; i++) {
    const srcFrame = Math.floor(i * downsampleRatio);
    const srcOffset = srcFrame * frameSize;
    if (srcOffset + frameSize > pcmData.length) break;

    const left = pcmData.readInt16LE(srcOffset);
    const right = pcmData.readInt16LE(srcOffset + bytesPerSample);
    const mono = Math.round((left + right) / 2);
    output.writeInt16LE(Math.max(-32768, Math.min(32767, mono)), i * outputBytesPerFrame);
  }

  return Buffer.concat([header, output]);
}

/**
 * Get duration of a PCM file in seconds.
 */
export function getPcmDuration(pcmData: Buffer): number {
  return pcmData.length / (PCM_SAMPLE_RATE * PCM_CHANNELS * (PCM_BIT_DEPTH / 8));
}

/**
 * Transcribe a PCM recording file using Gemini.
 */
export async function transcribeAudio(filename: string): Promise<TranscriptionResult> {
  if (!config.GOOGLE_API_KEY) {
    throw new Error('GOOGLE_API_KEY is not set. Cannot transcribe audio.');
  }

  const filePath = path.join(RECORDINGS_DIR, filename);
  if (!fs.existsSync(filePath)) {
    throw new Error(`Recording not found: ${filename}`);
  }

  const pcmData = fs.readFileSync(filePath);
  const durationSecs = getPcmDuration(pcmData);

  if (durationSecs < 0.5) {
    throw new Error('Recording is too short to transcribe.');
  }

  const wavData = pcmToWav(pcmData);

  // Gemini inline data limit is ~20MB
  if (wavData.length > 20 * 1024 * 1024) {
    throw new Error(`Recording too large (${(wavData.length / 1024 / 1024).toFixed(1)}MB). Max ~20MB (~10 min).`);
  }

  const base64Audio = wavData.toString('base64');
  const dataUrl = `data:audio/wav;base64,${base64Audio}`;

  // Send multimodal content (audio + text) through the AI gateway.
  // litellm supports base64 inline data via the image_url content part format.
  const result = await complete({
    messages: [{
      role: 'user',
      content: [
        { type: 'image_url', image_url: { url: dataUrl } },
        { type: 'text', text: 'Transcribe this audio recording accurately. Return only the transcription text. If multiple speakers are present, indicate speaker changes with "Speaker 1:", "Speaker 2:", etc.' },
      ] as unknown as string,  // gateway passes content through to litellm as-is
    }],
  });

  const text = result.text;
  if (!text) throw new Error('Transcription returned empty result.');

  return { text, filename, durationSecs };
}

// ── Full pipeline: transcribe → plan → launch ─────────────────────

export interface PipelineResult {
  transcription: string;
  planId: string;
  launched: boolean;
  error?: string;
}

/**
 * Full voice-to-code pipeline:
 * 1. Transcribe all saved PCM files
 * 2. Draft a plan from the combined transcription
 * 3. Save and launch the plan via the dashboard API
 *
 * @param savedFiles - Array of absolute paths to saved .pcm files
 * @param onProgress - Optional callback for status messages
 */
export async function transcribeAndLaunch(
  savedFiles: string[],
  onProgress?: (msg: string) => void,
): Promise<PipelineResult> {
  const log = onProgress || (() => {});

  if (!savedFiles.length) {
    return { transcription: '', planId: '', launched: false, error: 'No recordings to process.' };
  }

  if (!config.GOOGLE_API_KEY) {
    return { transcription: '', planId: '', launched: false, error: 'GOOGLE_API_KEY not set — cannot transcribe.' };
  }

  // 1. Transcribe all recordings
  log('🎙 Transcribing recordings...');
  const transcripts: string[] = [];
  for (const filePath of savedFiles) {
    try {
      const filename = path.basename(filePath);
      const result = await transcribeAudio(filename);
      const mins = Math.floor(result.durationSecs / 60);
      const secs = Math.round(result.durationSecs % 60);
      transcripts.push(`[${filename} — ${mins}m${secs}s]\n${result.text}`);
      log(`✅ Transcribed ${filename} (${mins}m${secs}s)`);
    } catch (err: any) {
      log(`⚠️ Failed to transcribe ${path.basename(filePath)}: ${err.message}`);
    }
  }

  if (!transcripts.length) {
    return { transcription: '', planId: '', launched: false, error: 'All transcriptions failed.' };
  }

  const fullTranscription = transcripts.join('\n\n');

  // 2. Draft a plan from the transcription
  log('📝 Drafting plan from voice discussion...');
  const refineResult = await api.refinePlan({
    message: `Create a detailed implementation plan based on this voice discussion transcript. Extract all tasks, requirements, and decisions mentioned:\n\n${fullTranscription}`,
  });

  if (refineResult._error) {
    return { transcription: fullTranscription, planId: '', launched: false, error: `Plan drafting failed: ${refineResult._error}` };
  }

  const planContent = refineResult.plan || refineResult.refined_plan || '';
  if (!planContent) {
    return { transcription: fullTranscription, planId: '', launched: false, error: 'AI returned empty plan.' };
  }

  // 3. Save the plan
  log('💾 Saving plan...');
  const created = await api.createPlan({
    title: 'Voice Recording Plan',
    content: planContent,
    workingDir: '.',
  });

  const planId = created.plan_id || '';
  if (!planId) {
    return { transcription: fullTranscription, planId: '', launched: false, error: 'Failed to save plan.' };
  }

  // 4. Launch the plan
  log('🚀 Launching plan...');
  const launchResult = await api.launchPlan(planId, planContent);

  if (launchResult._error) {
    return { transcription: fullTranscription, planId, launched: false, error: `Launch failed: ${launchResult._error}` };
  }

  log(`✅ Plan launched! ID: ${planId}`);
  return { transcription: fullTranscription, planId, launched: true };
}
