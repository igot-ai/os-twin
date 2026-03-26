const { expect } = require('chai');
const sinon = require('sinon');
const pingCommand = require('../src/commands/ping');

describe('Ping Command', () => {
  it('should have a valid data structure', () => {
    expect(pingCommand.data).to.exist;
    expect(pingCommand.data.name).to.equal('ping');
    expect(pingCommand.data.description).to.exist;
  });

  it('should reply with Pong and edit with latency', async () => {
    // Mock the interaction object
    const mockInteraction = {
      createdTimestamp: 1000,
      reply: sinon.stub().resolves({ createdTimestamp: 1050 }),
      editReply: sinon.stub().resolves(),
    };

    await pingCommand.execute(mockInteraction);

    expect(mockInteraction.reply.calledOnce).to.be.true;
    expect(mockInteraction.reply.firstCall.args[0]).to.deep.equal({
      content: 'Pinging...',
      fetchReply: true,
    });

    expect(mockInteraction.editReply.calledOnce).to.be.true;
    const expectedLatency = 50; // 1050 - 1000
    expect(mockInteraction.editReply.firstCall.args[0]).to.equal(`Pong! Latency is ${expectedLatency}ms.`);
  });
});
