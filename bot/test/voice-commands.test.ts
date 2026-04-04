
import { expect } from 'chai';
import sinon from 'sinon';
import { cleanupSession, sessions } from '../src/commands/join';
import { PassThrough } from 'node:stream';

import { execute as pingExecute } from '../src/commands/ping';

describe('Voice Commands Unit Tests', () => {
  describe('join.ts — cleanupSession', () => {
    it('returns empty if no session exists', async () => {
      const result = await cleanupSession('non-existent');
      expect(result.saved).to.be.an('array').with.lengthOf(0);
    });

    it('cleans up existing session and returns saved files', async () => {
      const guildId = 'g1';
      const pcmStream = new PassThrough();
      const fileStream = new PassThrough() as any;
      fileStream.end = (cb: any) => cb();
      
      const session: any = {
        channelId: 'c1',
        users: new Map([
          ['u1', { 
            username: 'user1', 
            pcmStream, 
            fileStream, 
            filePath: '/tmp/u1.pcm' 
          }]
        ])
      };
      
      sessions.set(guildId, session);
      
      const result = await cleanupSession(guildId);
      expect(result.saved).to.contain('/tmp/u1.pcm');
      expect(sessions.has(guildId)).to.be.false;
    });
  });

  describe('ping.ts — execute', () => {
    it('replies and then edits with latency', async () => {
      const interaction: any = {
        createdTimestamp: 1000,
        reply: sinon.stub().resolves({ createdTimestamp: 1100 }),
        editReply: sinon.stub().resolves(),
      };
      
      await pingExecute(interaction);
      expect(interaction.reply.calledOnce).to.be.true;
      expect(interaction.editReply.calledOnce).to.be.true;
      expect(interaction.editReply.firstCall.args[0]).to.include('100ms');
    });
  });
});
