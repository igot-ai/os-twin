import { expect } from 'chai';
import { mdConvert, chunk, detectEpicRef, guessAssetType } from '../src/connectors/utils';

describe('connectors/utils', () => {

  // ── mdConvert ──────────────────────────────────────────────────────

  describe('mdConvert', () => {
    it('converts single *bold* to **bold**', () => {
      expect(mdConvert('*bold*')).to.equal('**bold**');
    });

    it('leaves **already bold** unchanged', () => {
      expect(mdConvert('**already bold**')).to.equal('**already bold**');
    });

    it('leaves normal text unchanged', () => {
      expect(mdConvert('normal text')).to.equal('normal text');
    });

    it('converts *multiple* bold segments in one string', () => {
      expect(mdConvert('*multiple* words *bold*')).to.equal('**multiple** words **bold**');
    });

    it('returns empty string for empty input', () => {
      expect(mdConvert('')).to.equal('');
    });

    it('does not double-convert ***triple***', () => {
      const result = mdConvert('***triple***');
      // ***triple*** has adjacent asterisks, so the lookbehind/lookahead
      // should prevent the single-star regex from matching inside triple stars.
      expect(result).to.not.include('****');
    });

    it('handles mixed bold and plain text', () => {
      expect(mdConvert('hello *world* and *foo*')).to.equal('hello **world** and **foo**');
    });

    it('handles text with no asterisks', () => {
      expect(mdConvert('no formatting here')).to.equal('no formatting here');
    });
  });

  // ── chunk ──────────────────────────────────────────────────────────

  describe('chunk', () => {
    it('returns single chunk for short text within limit', () => {
      const result = chunk('hello world', 100);
      expect(result).to.deep.equal(['hello world']);
    });

    it('returns [""] for empty text', () => {
      const result = chunk('', 100);
      expect(result).to.deep.equal(['']);
    });

    it('splits long text at newline boundary', () => {
      const text = 'line one\nline two\nline three';
      // limit=17 fits "line one\nline two" (17 chars) but not the rest
      const result = chunk(text, 17);
      expect(result.length).to.be.greaterThan(1);
      // First chunk should contain "line one\nline two" or split at a newline
      expect(result[0]).to.include('line one');
    });

    it('splits at space when no newline found within limit', () => {
      const text = 'word1 word2 word3 word4 word5';
      const result = chunk(text, 12);
      expect(result.length).to.be.greaterThan(1);
      // Should split at a space boundary, not in the middle of a word
      for (const c of result) {
        // No chunk should start or end mid-word (except possibly last)
        expect(c.length).to.be.at.most(12);
      }
    });

    it('hard splits at limit when no spaces or newlines', () => {
      const text = 'abcdefghijklmnop'; // 16 chars, no spaces
      const result = chunk(text, 5);
      expect(result.length).to.be.greaterThan(1);
      expect(result[0]).to.have.lengthOf(5);
    });

    it('returns single chunk when text is exactly limit length', () => {
      const text = '12345';
      const result = chunk(text, 5);
      expect(result).to.deep.equal(['12345']);
    });

    it('handles text shorter than limit', () => {
      const result = chunk('hi', 1000);
      expect(result).to.deep.equal(['hi']);
    });

    it('handles multi-line text with varied split points', () => {
      const text = 'aaa\nbbb\nccc\nddd';
      const result = chunk(text, 7);
      expect(result.length).to.be.greaterThanOrEqual(2);
      // Reassembled text should preserve all content (accounting for trimmed whitespace)
      const reassembled = result.join(' ').replace(/\s+/g, ' ');
      expect(reassembled).to.include('aaa');
      expect(reassembled).to.include('ddd');
    });
  });

  // ── detectEpicRef ──────────────────────────────────────────────────

  describe('detectEpicRef', () => {
    it('detects EPIC-001 in text', () => {
      expect(detectEpicRef('EPIC-001')).to.equal('EPIC-001');
    });

    it('detects lowercase epic-42 and uppercases it', () => {
      expect(detectEpicRef('epic-42')).to.equal('EPIC-42');
    });

    it('returns undefined when no epic reference found', () => {
      expect(detectEpicRef('no epic here')).to.be.undefined;
    });

    it('returns undefined for empty string', () => {
      expect(detectEpicRef('')).to.be.undefined;
    });

    it('returns first match when multiple epic refs present', () => {
      const result = detectEpicRef('multiple EPIC-001 and EPIC-002');
      expect(result).to.equal('EPIC-001');
    });

    it('detects epic ref embedded in a sentence', () => {
      expect(detectEpicRef('Working on EPIC-123 today')).to.equal('EPIC-123');
    });

    it('handles mixed case Epic-007', () => {
      expect(detectEpicRef('check Epic-007')).to.equal('EPIC-007');
    });
  });

  // ── guessAssetType ─────────────────────────────────────────────────

  describe('guessAssetType', () => {
    it('returns "design-mockup" for .png with image/png mime', () => {
      expect(guessAssetType('mockup.png', 'image/png')).to.equal('design-mockup');
    });

    it('returns "design-mockup" for plain image with image/ mime type', () => {
      expect(guessAssetType('photo.jpg', 'image/jpeg')).to.equal('design-mockup');
    });

    it('returns "api-spec" for api-spec.yaml', () => {
      expect(guessAssetType('api-spec.yaml')).to.equal('api-spec');
    });

    it('returns "test-data" for test_data.csv', () => {
      expect(guessAssetType('test_data.csv')).to.equal('test-data');
    });

    it('returns "test-data" for plain .csv files', () => {
      expect(guessAssetType('data.csv')).to.equal('test-data');
    });

    it('returns "config" for config.env', () => {
      expect(guessAssetType('config.env')).to.equal('config');
    });

    it('returns "config" for .env files', () => {
      expect(guessAssetType('.env')).to.equal('config');
    });

    it('returns "config" for .toml files', () => {
      expect(guessAssetType('settings.toml')).to.equal('config');
    });

    it('returns "reference-doc" for readme.md', () => {
      expect(guessAssetType('readme.md')).to.equal('reference-doc');
    });

    it('returns "reference-doc" for .pdf files', () => {
      expect(guessAssetType('guide.pdf')).to.equal('reference-doc');
    });

    it('returns "reference-doc" for .txt files', () => {
      expect(guessAssetType('notes.txt')).to.equal('reference-doc');
    });

    it('returns "media" for video.mp4 with video/mp4 mime', () => {
      expect(guessAssetType('video.mp4', 'video/mp4')).to.equal('media');
    });

    it('returns "media" for audio files', () => {
      expect(guessAssetType('track.mp3', 'audio/mpeg')).to.equal('media');
    });

    it('returns "other" for unknown file types', () => {
      expect(guessAssetType('random.xyz')).to.equal('other');
    });

    it('returns "design-mockup" for .fig files (Figma)', () => {
      expect(guessAssetType('ui-wireframe.fig')).to.equal('design-mockup');
    });

    it('returns "design-mockup" for .sketch files', () => {
      expect(guessAssetType('design.sketch')).to.equal('design-mockup');
    });

    it('returns "api-spec" for swagger files', () => {
      expect(guessAssetType('swagger.json')).to.equal('api-spec');
    });

    it('returns "api-spec" for openapi files', () => {
      expect(guessAssetType('openapi.yaml')).to.equal('api-spec');
    });

    it('handles case insensitivity in filename', () => {
      expect(guessAssetType('API-SPEC.YAML')).to.equal('api-spec');
    });

    it('handles case insensitivity in mime type', () => {
      expect(guessAssetType('photo.jpg', 'Image/JPEG')).to.equal('design-mockup');
    });

    it('works without mime type argument', () => {
      expect(guessAssetType('readme.md')).to.equal('reference-doc');
    });
  });
});
