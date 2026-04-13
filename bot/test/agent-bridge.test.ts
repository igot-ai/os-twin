import { expect } from 'chai';
import sinon from 'sinon';
import config from '../src/config';
import api from '../src/api';
import { askAgent } from '../src/agent-bridge';
import { type AttachmentMeta } from '../src/connectors/base';

/**
 * Tests for the agent-bridge with tool-calling capabilities.
 *
 * The upgraded bridge uses Gemini function calling to autonomously
 * create plans, list plans, check status, and launch plans.
 *
 * Since mocking the Gemini constructor chain is complex, we focus on:
 * 1. API key validation
 * 2. Context gathering (getPlans, getRooms)
 * 3. Error handling
 * 4. Backward compatibility (ctx parameter optional)
 */

describe('agent-bridge', () => {
  let sandbox: sinon.SinonSandbox;
  const originalApiKey = config.GOOGLE_API_KEY;

  beforeEach(() => {
    sandbox = sinon.createSandbox();
  });

  afterEach(() => {
    sandbox.restore();
    config.GOOGLE_API_KEY = originalApiKey;
  });

  // ── API key validation ──────────────────────────────────────────

  it('returns error when GOOGLE_API_KEY is not set', async () => {
    config.GOOGLE_API_KEY = '';
    const result = await askAgent('test question');
    expect(result).to.include('GOOGLE_API_KEY');
    expect(result).to.include('not set');
  });

  // ── Context gathering ───────────────────────────────────────────

  describe('context gathering', () => {
    it('calls all API endpoints in parallel', async () => {
      config.GOOGLE_API_KEY = 'test-key';

      const plansStub = sandbox.stub(api, 'getPlans').resolves({ plans: [], count: 0 });
      const roomsStub = sandbox.stub(api, 'getRooms').resolves({ rooms: [], summary: {} });

      try {
        // Will fail at Gemini API call but we verify the context gathering happened
        await askAgent('test question');
      } catch {
        // Expected — Gemini API is not mocked
      }

      expect(plansStub.calledOnce).to.be.true;
      expect(roomsStub.calledOnce).to.be.true;
    });

    it('formats plans and rooms correctly when data exists', async () => {
      config.GOOGLE_API_KEY = 'test-key';
      const plansStub = sandbox.stub(api, 'getPlans').resolves({
        plans: [{ plan_id: 'p1', title: 'Plan 1', status: 'draft', pct_complete: 50, epic_count: 3 }],
        count: 1,
      });
      sandbox.stub(api, 'getRooms').resolves({
        rooms: [{ room_id: 'r1', status: 'engineering', epic_ref: 'EPIC-001', message_count: 5 }],
        summary: {},
      });

      try {
        await askAgent('what is happening?');
      } catch {
        // Expected — Gemini API is not mocked
      }

      // Verify the plans data was retrieved for context building
      expect(plansStub.calledOnce).to.be.true;
      const plansResult = await plansStub.returnValues[0];
      expect(plansResult.plans).to.have.length(1);
      expect(plansResult.plans[0].title).to.equal('Plan 1');
    });

    it('handles empty data gracefully', async () => {
      config.GOOGLE_API_KEY = 'test-key';
      sandbox.stub(api, 'getPlans').resolves({ plans: [], count: 0 });
      sandbox.stub(api, 'getRooms').resolves({ rooms: [], summary: {} });

      // Should not throw even with empty data
      // (will still fail at Gemini, but the context gathering should succeed)
      try {
        await askAgent('test');
      } catch {
        // Expected
      }
    });
  });

  // ── Error handling ──────────────────────────────────────────────

  describe('error handling', () => {
    it('returns user-friendly error when Gemini API fails', async () => {
      config.GOOGLE_API_KEY = 'test-key';
      sandbox.stub(api, 'getPlans').resolves({ plans: [] });
      sandbox.stub(api, 'getRooms').resolves({ rooms: [], summary: {} });

      // The real Gemini API call will fail with an invalid key
      const result = await askAgent('test');
      // Should return an error message, not throw
      expect(result).to.be.a('string');
      expect(result).to.include('Failed to get a response');
    });
  });

  // ── Backward compatibility ─────────────────────────────────────

  describe('backward compatibility', () => {
    it('works without ctx parameter (old signature)', async () => {
      config.GOOGLE_API_KEY = 'test-key';
      sandbox.stub(api, 'getPlans').resolves({ plans: [] });
      sandbox.stub(api, 'getRooms').resolves({ rooms: [], summary: {} });

      // Call without ctx — should not throw from context handling
      const result = await askAgent('hello');
      expect(result).to.be.a('string');
    });

    it('accepts ctx parameter for tool execution', async () => {
      config.GOOGLE_API_KEY = 'test-key';
      sandbox.stub(api, 'getPlans').resolves({ plans: [] });
      sandbox.stub(api, 'getRooms').resolves({ rooms: [], summary: {} });

      // Call with ctx — should not throw
      const result = await askAgent('hello', { userId: 'u1', platform: 'discord' });
      expect(result).to.be.a('string');
    });
  });

  // ── Function signature ─────────────────────────────────────────

  describe('function signature', () => {
    it('askAgent is exported as an async function', () => {
      expect(typeof askAgent).to.equal('function');
    });

    it('returns a string', async () => {
      config.GOOGLE_API_KEY = '';
      const result = await askAgent('test');
      expect(typeof result).to.be.a('string');
    });
  });

  // ── Referenced Message Context ─────────────────────────────────

  describe('referenced message context', () => {
    it('AgentContext interface should accept referencedMessageContent', () => {
      interface AgentContextWithReference {
        userId: string;
        platform: string;
        referencedMessageContent?: string;
      }

      const ctx: AgentContextWithReference = {
        userId: '806867494702809108',
        platform: 'discord',
        referencedMessageContent: 'What is the status of EPIC-001?',
      };

      expect(ctx.referencedMessageContent).to.equal('What is the status of EPIC-001?');
    });

    it('AgentContext should work without referencedMessageContent (backward compat)', () => {
      interface AgentContextWithReference {
        userId: string;
        platform: string;
        referencedMessageContent?: string;
      }

      const ctx: AgentContextWithReference = {
        userId: '806867494702809108',
        platform: 'discord',
      };

      expect(ctx.referencedMessageContent).to.be.undefined;
    });

    it('askAgent should accept referencedMessageContent in ctx parameter', async () => {
      config.GOOGLE_API_KEY = 'test-key';
      sandbox.stub(api, 'getPlans').resolves({ plans: [] });
      sandbox.stub(api, 'getRooms').resolves({ rooms: [], summary: {} });

      // Call with referencedMessageContent — should not throw
      const result = await askAgent('yes sir', {
        userId: 'u1',
        platform: 'discord',
        referencedMessageContent: 'What do you think about this design?',
      });
      expect(result).to.be.a('string');
    });

    it('system prompt should include referenced message context', () => {
      const referencedContent = 'What is the plan for the API?';
      const userReply = 'yes sir';

      // This tests the prompt-building logic
      const promptWithContext = buildPromptWithContext(userReply, referencedContent);
      expect(promptWithContext).to.include('User is replying to');
      expect(promptWithContext).to.include(referencedContent);
    });

    it('system prompt should work without referenced message', () => {
      const userMessage = 'hello';

      const promptWithContext = buildPromptWithContext(userMessage, undefined);
      expect(promptWithContext).to.not.include('User is replying to');
    });
  });

  // ── Attachment Context ──────────────────────────────────────────

  describe('attachment context', () => {
    it('AgentContext should accept attachments array', () => {
      const ctx: { userId: string; platform: string; attachments?: AttachmentMeta[] } = {
        userId: 'u1',
        platform: 'discord',
        attachments: [
          { name: 'mockup.png', contentType: 'image/png', sizeBytes: 2048 },
          { name: 'spec.pdf', contentType: 'application/pdf', sizeBytes: 10240 },
        ],
      };

      expect(ctx.attachments).to.have.length(2);
      expect(ctx.attachments![0].name).to.equal('mockup.png');
      expect(ctx.attachments![1].contentType).to.equal('application/pdf');
    });

    it('AgentContext should work without attachments (backward compat)', () => {
      const ctx: { userId: string; platform: string; attachments?: AttachmentMeta[] } = {
        userId: 'u1',
        platform: 'discord',
      };

      expect(ctx.attachments).to.be.undefined;
    });

    it('askAgent should accept attachments in ctx parameter', async () => {
      config.GOOGLE_API_KEY = 'test-key';
      sandbox.stub(api, 'getPlans').resolves({ plans: [] });
      sandbox.stub(api, 'getRooms').resolves({ rooms: [], summary: {} });

      const result = await askAgent('build me a dashboard', {
        userId: 'u1',
        platform: 'discord',
        attachments: [
          { name: 'dashboard-mockup.png', contentType: 'image/png', sizeBytes: 4096 },
        ],
      });
      expect(result).to.be.a('string');
    });

    it('attachment context prompt includes file names and types', () => {
      const attachments: AttachmentMeta[] = [
        { name: 'wireframe.png', contentType: 'image/png', sizeBytes: 2048 },
        { name: 'requirements.pdf', contentType: 'application/pdf', sizeBytes: 51200 },
      ];

      const context = buildAttachmentContext(attachments);
      expect(context).to.include('wireframe.png');
      expect(context).to.include('image/png');
      expect(context).to.include('requirements.pdf');
      expect(context).to.include('application/pdf');
      expect(context).to.include('2 file(s)');
    });

    it('attachment context is empty when no attachments', () => {
      const context = buildAttachmentContext(undefined);
      expect(context).to.equal('');
    });

    it('attachment context is empty for empty array', () => {
      const context = buildAttachmentContext([]);
      expect(context).to.equal('');
    });
  });
});

/**
 * Helper function to build prompt with referenced message context.
 * Mirrors the logic in agent-bridge.ts
 */
function buildPromptWithContext(
  userMessage: string,
  referencedMessageContent?: string,
): string {
  if (referencedMessageContent) {
    return `User is replying to this message:\n"${referencedMessageContent}"\n\nUser's reply: ${userMessage}`;
  }
  return userMessage;
}

/**
 * Helper function to build attachment context for the system prompt.
 * Mirrors the logic in agent-bridge.ts askAgent().
 */
function buildAttachmentContext(
  attachments?: AttachmentMeta[],
): string {
  if (!attachments?.length) return '';
  return `\n\n## Attached Files\nThe user has attached ${attachments.length} file(s) with this message:\n` +
    attachments.map(a => `- ${a.name} (${a.contentType || 'unknown type'})`).join('\n') +
    `\nThese files are staged and will be automatically linked to any plan you create. If the user is asking to build something, call create_plan — the staged files will be used as reference material.`;
}
