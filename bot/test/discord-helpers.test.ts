/**
 * Tests for Discord adapter helper functions.
 *
 * Tests the exported mdConvert and chunk utility functions.
 */

import { expect } from 'chai';
import { mdConvert, chunk } from '../src/discord';

describe('discord helpers', () => {
  describe('mdConvert', () => {
    it('converts single *bold* to **bold**', () => {
      expect(mdConvert('*hello*')).to.equal('**hello**');
    });

    it('converts multiple bold segments', () => {
      expect(mdConvert('*foo* and *bar*')).to.equal('**foo** and **bar**');
    });

    it('does not double-convert existing **bold**', () => {
      expect(mdConvert('**already bold**')).to.equal('**already bold**');
    });

    it('handles text without bold markers', () => {
      expect(mdConvert('plain text')).to.equal('plain text');
    });

    it('handles inline code with backticks unchanged', () => {
      expect(mdConvert('`code here`')).to.equal('`code here`');
    });

    it('handles mixed content', () => {
      const input = '*Active:* `5` rooms, *Passed:* `3`';
      const output = mdConvert(input);
      expect(output).to.include('**Active:**');
      expect(output).to.include('`5`');
    });
  });

  describe('chunk', () => {
    it('returns single chunk for short text', () => {
      const result = chunk('hello world', 2000);
      expect(result).to.deep.equal(['hello world']);
    });

    it('splits on newline when possible', () => {
      const line = 'a'.repeat(100);
      const text = `${line}\n${line}\n${line}`;
      const result = chunk(text, 210);
      expect(result.length).to.be.greaterThan(1);
      for (const c of result) {
        expect(c.length).to.be.at.most(210);
      }
    });

    it('splits on space when no newline', () => {
      const text = 'word '.repeat(500);
      const result = chunk(text, 2000);
      expect(result.length).to.be.greaterThan(1);
      for (const c of result) {
        expect(c.length).to.be.at.most(2000);
      }
    });

    it('hard-splits when no whitespace', () => {
      const text = 'x'.repeat(3000);
      const result = chunk(text, 2000);
      expect(result).to.have.lengthOf(2);
      expect(result[0]).to.have.lengthOf(2000);
      expect(result[1]).to.have.lengthOf(1000);
    });

    it('handles empty text', () => {
      const result = chunk('', 2000);
      expect(result).to.deep.equal(['']);
    });

    it('handles text exactly at limit', () => {
      const text = 'a'.repeat(2000);
      const result = chunk(text, 2000);
      expect(result).to.deep.equal([text]);
    });
  });
});
