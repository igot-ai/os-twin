/**
 * Tests for the audio-transcript module.
 *
 * Tests PCM→WAV conversion, recording listing, transcription,
 * and the full voice-to-code pipeline (transcribe → plan → launch).
 */

import { expect } from 'chai';
import sinon from 'sinon';
import fs from 'fs';
import path from 'path';
import { pcmToWav, getPcmDuration, listRecordings, transcribeAudio, transcribeAndLaunch } from '../src/audio-transcript';
import api from '../src/api';
import config from '../src/config';

describe('audio-transcript', () => {
  // ── pcmToWav ────────────────────────────────────────────────────

  describe('pcmToWav', () => {
    it('produces a valid WAV header', () => {
      const pcm = Buffer.alloc(400);
      for (let i = 0; i < 100; i++) {
        pcm.writeInt16LE(Math.floor(Math.sin(i * 0.1) * 1000), i * 4);
        pcm.writeInt16LE(Math.floor(Math.cos(i * 0.1) * 1000), i * 4 + 2);
      }

      const wav = pcmToWav(pcm);

      expect(wav.slice(0, 4).toString()).to.equal('RIFF');
      expect(wav.slice(8, 12).toString()).to.equal('WAVE');
      expect(wav.slice(12, 16).toString()).to.equal('fmt ');
      expect(wav.slice(36, 40).toString()).to.equal('data');
      expect(wav.readUInt16LE(22)).to.equal(1);     // mono
      expect(wav.readUInt32LE(24)).to.equal(16000);  // 16kHz
      expect(wav.readUInt16LE(34)).to.equal(16);     // 16-bit
    });

    it('downsamples from 48kHz stereo to 16kHz mono', () => {
      const frames = 480;
      const pcm = Buffer.alloc(frames * 4);
      for (let i = 0; i < frames; i++) {
        pcm.writeInt16LE(1000, i * 4);
        pcm.writeInt16LE(1000, i * 4 + 2);
      }

      const wav = pcmToWav(pcm);
      const dataSize = wav.readUInt32LE(40);
      const outputFrames = dataSize / 2;
      expect(outputFrames).to.equal(160);
    });

    it('averages stereo channels to mono', () => {
      const pcm3 = Buffer.alloc(12);
      for (let i = 0; i < 3; i++) {
        pcm3.writeInt16LE(1000, i * 4);
        pcm3.writeInt16LE(3000, i * 4 + 2);
      }
      const wav3 = pcmToWav(pcm3);
      const dataSize = wav3.readUInt32LE(40);
      if (dataSize >= 2) {
        const sample = wav3.readInt16LE(44);
        expect(sample).to.equal(2000);
      }
    });

    it('clamps output to 16-bit range', () => {
      const pcm = Buffer.alloc(12);
      for (let i = 0; i < 3; i++) {
        pcm.writeInt16LE(32767, i * 4);
        pcm.writeInt16LE(32767, i * 4 + 2);
      }
      const wav = pcmToWav(pcm);
      const dataSize = wav.readUInt32LE(40);
      if (dataSize >= 2) {
        const sample = wav.readInt16LE(44);
        expect(sample).to.be.at.most(32767);
        expect(sample).to.be.at.least(-32768);
      }
    });

    it('handles empty PCM buffer', () => {
      const wav = pcmToWav(Buffer.alloc(0));
      expect(wav.length).to.equal(44);
      expect(wav.readUInt32LE(40)).to.equal(0);
    });
  });

  // ── getPcmDuration ──────────────────────────────────────────────

  describe('getPcmDuration', () => {
    it('calculates duration from buffer size', () => {
      const oneSecond = Buffer.alloc(192000);
      expect(getPcmDuration(oneSecond)).to.equal(1);
    });

    it('returns 0 for empty buffer', () => {
      expect(getPcmDuration(Buffer.alloc(0))).to.equal(0);
    });

    it('calculates fractional seconds', () => {
      const halfSecond = Buffer.alloc(96000);
      expect(getPcmDuration(halfSecond)).to.equal(0.5);
    });
  });

  // ── listRecordings ──────────────────────────────────────────────

  describe('listRecordings', () => {
    it('returns an array', () => {
      const files = listRecordings();
      expect(files).to.be.an('array');
    });

    it('only includes .pcm files', () => {
      const files = listRecordings();
      for (const f of files) {
        expect(f).to.match(/\.pcm$/);
      }
    });
  });

  // ── transcribeAudio ─────────────────────────────────────────────

  describe('transcribeAudio', () => {
    it('throws when GOOGLE_API_KEY is not set', async () => {
      const origKey = config.GOOGLE_API_KEY;
      config.GOOGLE_API_KEY = '';
      try {
        await transcribeAudio('nonexistent.pcm');
        expect.fail('should have thrown');
      } catch (err: any) {
        expect(err.message).to.include('GOOGLE_API_KEY');
      } finally {
        config.GOOGLE_API_KEY = origKey;
      }
    });

    it('throws for missing file', async () => {
      const origKey = config.GOOGLE_API_KEY;
      config.GOOGLE_API_KEY = 'test-key';
      try {
        await transcribeAudio('does-not-exist.pcm');
        expect.fail('should have thrown');
      } catch (err: any) {
        expect(err.message).to.include('not found');
      } finally {
        config.GOOGLE_API_KEY = origKey;
      }
    });
  });

  // ── transcribeAndLaunch (full pipeline) ─────────────────────────

  describe('transcribeAndLaunch', () => {
    let sandbox: sinon.SinonSandbox;
    const origKey = config.GOOGLE_API_KEY;
    const RECORDINGS_DIR = path.resolve(__dirname, '../recordings');

    // Create a small test PCM file (1 second of silence)
    const TEST_FILE = path.join(RECORDINGS_DIR, '_test-pipeline.pcm');

    before(() => {
      if (!fs.existsSync(RECORDINGS_DIR)) fs.mkdirSync(RECORDINGS_DIR, { recursive: true });
      // 1 second of PCM: 48kHz * 2ch * 2bytes = 192000 bytes
      fs.writeFileSync(TEST_FILE, Buffer.alloc(192000));
    });

    after(() => {
      config.GOOGLE_API_KEY = origKey;
      try { fs.unlinkSync(TEST_FILE); } catch { /* ok */ }
    });

    beforeEach(() => {
      sandbox = sinon.createSandbox();
    });

    afterEach(() => {
      sandbox.restore();
      config.GOOGLE_API_KEY = origKey;
    });

    it('returns error when no files provided', async () => {
      const result = await transcribeAndLaunch([]);
      expect(result.launched).to.be.false;
      expect(result.error).to.include('No recordings');
    });

    it('returns error when GOOGLE_API_KEY is not set', async () => {
      config.GOOGLE_API_KEY = '';
      const result = await transcribeAndLaunch([TEST_FILE]);
      expect(result.launched).to.be.false;
      expect(result.error).to.include('GOOGLE_API_KEY');
    });

    it('runs full pipeline: transcribe → plan → launch', async () => {
      config.GOOGLE_API_KEY = 'test-key';

      // Mock the Gemini transcription (stub the module-level function)
      // Since transcribeAudio reads the file and calls Gemini, we stub at the API level
      // We need to stub the GoogleGenerativeAI - let's stub fetch instead
      const fetchStub = sandbox.stub(global, 'fetch').resolves(
        new Response(JSON.stringify({
          candidates: [{ content: { parts: [{ text: 'Build a REST API with auth and database' }] } }],
        }), { status: 200, headers: { 'content-type': 'application/json' } })
      );

      sandbox.stub(api, 'refinePlan').resolves({
        plan: '# Plan: REST API\n## Epic 1: Auth\n## Epic 2: Database',
        explanation: 'Created plan from voice discussion',
      });
      sandbox.stub(api, 'createPlan').resolves({ plan_id: 'voice-plan-1234' });
      sandbox.stub(api, 'launchPlan').resolves({ status: 'launched' });

      const progress: string[] = [];
      const result = await transcribeAndLaunch([TEST_FILE], (msg) => progress.push(msg));

      expect(result.launched).to.be.true;
      expect(result.planId).to.equal('voice-plan-1234');
      expect(result.transcription).to.include('REST API');
      expect(result.error).to.be.undefined;

      // Verify progress messages
      expect(progress.some(m => m.includes('Transcribing'))).to.be.true;
      expect(progress.some(m => m.includes('Drafting'))).to.be.true;
      expect(progress.some(m => m.includes('Launching'))).to.be.true;
      expect(progress.some(m => m.includes('launched'))).to.be.true;
    });

    it('returns error when plan drafting fails', async () => {
      config.GOOGLE_API_KEY = 'test-key';

      sandbox.stub(global, 'fetch').resolves(
        new Response(JSON.stringify({
          candidates: [{ content: { parts: [{ text: 'Some discussion' }] } }],
        }), { status: 200, headers: { 'content-type': 'application/json' } })
      );

      sandbox.stub(api, 'refinePlan').resolves({ _error: 'AI service unavailable' });

      const result = await transcribeAndLaunch([TEST_FILE]);
      expect(result.launched).to.be.false;
      expect(result.error).to.include('Plan drafting failed');
      expect(result.transcription).to.not.be.empty;
    });

    it('returns error when plan creation fails', async () => {
      config.GOOGLE_API_KEY = 'test-key';

      sandbox.stub(global, 'fetch').resolves(
        new Response(JSON.stringify({
          candidates: [{ content: { parts: [{ text: 'Discussion about features' }] } }],
        }), { status: 200, headers: { 'content-type': 'application/json' } })
      );

      sandbox.stub(api, 'refinePlan').resolves({ plan: '# Plan content' });
      sandbox.stub(api, 'createPlan').resolves({ _error: 'Storage full' } as any);

      const result = await transcribeAndLaunch([TEST_FILE]);
      expect(result.launched).to.be.false;
      expect(result.error).to.include('Failed to save plan');
    });

    it('returns error when launch fails', async () => {
      config.GOOGLE_API_KEY = 'test-key';

      sandbox.stub(global, 'fetch').resolves(
        new Response(JSON.stringify({
          candidates: [{ content: { parts: [{ text: 'Plan the backend' }] } }],
        }), { status: 200, headers: { 'content-type': 'application/json' } })
      );

      sandbox.stub(api, 'refinePlan').resolves({ plan: '# Plan' });
      sandbox.stub(api, 'createPlan').resolves({ plan_id: 'plan-abc' });
      sandbox.stub(api, 'launchPlan').resolves({ _error: 'Manager not running' });

      const result = await transcribeAndLaunch([TEST_FILE]);
      expect(result.launched).to.be.false;
      expect(result.planId).to.equal('plan-abc');
      expect(result.error).to.include('Launch failed');
    });

    it('returns error when AI returns empty plan', async () => {
      config.GOOGLE_API_KEY = 'test-key';

      sandbox.stub(global, 'fetch').resolves(
        new Response(JSON.stringify({
          candidates: [{ content: { parts: [{ text: 'Some talk' }] } }],
        }), { status: 200, headers: { 'content-type': 'application/json' } })
      );

      sandbox.stub(api, 'refinePlan').resolves({ plan: '' });

      const result = await transcribeAndLaunch([TEST_FILE]);
      expect(result.launched).to.be.false;
      expect(result.error).to.include('empty plan');
    });

    it('continues when one of multiple files fails transcription', async () => {
      config.GOOGLE_API_KEY = 'test-key';

      sandbox.stub(global, 'fetch').resolves(
        new Response(JSON.stringify({
          candidates: [{ content: { parts: [{ text: 'Valid transcription' }] } }],
        }), { status: 200, headers: { 'content-type': 'application/json' } })
      );

      sandbox.stub(api, 'refinePlan').resolves({ plan: '# Plan from partial' });
      sandbox.stub(api, 'createPlan').resolves({ plan_id: 'partial-plan' });
      sandbox.stub(api, 'launchPlan').resolves({ status: 'launched' });

      const progress: string[] = [];
      // First file doesn't exist, second does
      const result = await transcribeAndLaunch(
        ['/nonexistent/fake.pcm', TEST_FILE],
        (msg) => progress.push(msg),
      );

      expect(result.launched).to.be.true;
      // Should have a warning about the failed file
      expect(progress.some(m => m.includes('Failed to transcribe'))).to.be.true;
      // But still transcribed the valid one
      expect(progress.some(m => m.includes('Transcribed'))).to.be.true;
    });

    it('returns error when all transcriptions fail', async () => {
      config.GOOGLE_API_KEY = 'test-key';

      const result = await transcribeAndLaunch(['/nonexistent/a.pcm', '/nonexistent/b.pcm']);
      expect(result.launched).to.be.false;
      expect(result.error).to.include('All transcriptions failed');
    });

    it('calls onProgress callbacks at each stage', async () => {
      config.GOOGLE_API_KEY = 'test-key';

      sandbox.stub(global, 'fetch').resolves(
        new Response(JSON.stringify({
          candidates: [{ content: { parts: [{ text: 'Hello world' }] } }],
        }), { status: 200, headers: { 'content-type': 'application/json' } })
      );

      sandbox.stub(api, 'refinePlan').resolves({ plan: '# Plan' });
      sandbox.stub(api, 'createPlan').resolves({ plan_id: 'p1' });
      sandbox.stub(api, 'launchPlan').resolves({});

      const progress: string[] = [];
      await transcribeAndLaunch([TEST_FILE], (msg) => progress.push(msg));

      // Should have messages for each pipeline stage
      expect(progress.length).to.be.at.least(4);
      expect(progress[0]).to.include('Transcribing');
    });
  });
});
