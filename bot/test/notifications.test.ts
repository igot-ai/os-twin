import { expect } from 'chai';
import sinon from 'sinon';
import { NotificationRouter } from '../src/notifications';
import { registry } from '../src/connectors/registry';
import { Connector } from '../src/connectors/base';

describe('NotificationRouter', () => {
  let sandbox: sinon.SinonSandbox;
  let router: NotificationRouter;
  let mockConnector: any;

  beforeEach(() => {
    sandbox = sinon.createSandbox();
    mockConnector = {
      platform: 'telegram',
      status: 'connected',
      sendMessage: sandbox.stub().resolves(),
    };
    sandbox.stub(registry, 'getConnector').returns(mockConnector);
    sandbox.stub(registry, 'getAllConfigs').returns([
      {
        platform: 'telegram',
        enabled: true,
        authorized_users: ['u1'],
        notification_preferences: { events: [], enabled: true },
        credentials: {},
        settings: {},
        pairing_code: '',
      } as any,
    ]);
    router = new NotificationRouter(registry);
  });

  afterEach(() => {
    sandbox.restore();
  });

  it('maps room_created to plan_started', async () => {
    const handleEvent = (router as any).handleDashboardEvent.bind(router);
    handleEvent({
      type: 'room_created',
      data: { room: { room_id: 'room-1', task_ref: 'Task 1' } },
    });

    // Wait a bit for async routing
    await new Promise(resolve => setTimeout(resolve, 10));

    expect(mockConnector.sendMessage.calledOnce).to.be.true;
    expect(mockConnector.sendMessage.firstCall.args[0]).to.equal('u1');
    expect(mockConnector.sendMessage.firstCall.args[1].text).to.include('New War-Room Created');
    expect(mockConnector.sendMessage.firstCall.args[1].text).to.include('room-1');
  });

  it('maps room_updated with status passed to epic_passed', async () => {
    const handleEvent = (router as any).handleDashboardEvent.bind(router);
    handleEvent({
      type: 'room_updated',
      data: { room: { room_id: 'room-1', status: 'passed' } },
    });

    await new Promise(resolve => setTimeout(resolve, 10));

    expect(mockConnector.sendMessage.calledOnce).to.be.true;
    expect(mockConnector.sendMessage.firstCall.args[1].text).to.include('EPIC Passed');
  });

  it('maps room_updated with status failed to epic_failed', async () => {
    const handleEvent = (router as any).handleDashboardEvent.bind(router);
    handleEvent({
      type: 'room_updated',
      data: { room: { room_id: 'room-1', status: 'failed' } },
    });
    await new Promise(resolve => setTimeout(resolve, 10));
    expect(mockConnector.sendMessage.firstCall.args[1].text).to.include('EPIC Failed');
  });

  it('maps room_updated with status fixing to epic_retry', async () => {
    const handleEvent = (router as any).handleDashboardEvent.bind(router);
    handleEvent({
      type: 'room_updated',
      data: { room: { room_id: 'room-1', status: 'fixing' } },
    });
    await new Promise(resolve => setTimeout(resolve, 10));
    expect(mockConnector.sendMessage.firstCall.args[1].text).to.include('EPIC Retrying');
  });

  it('maps room_updated with status pending_feedback to feedback_needed', async () => {
    const handleEvent = (router as any).handleDashboardEvent.bind(router);
    handleEvent({
      type: 'room_updated',
      data: { room: { room_id: 'room-1', status: 'pending_feedback' } },
    });
    await new Promise(resolve => setTimeout(resolve, 10));
    expect(mockConnector.sendMessage.firstCall.args[1].text).to.include('Feedback Needed');
  });

  it('maps room_updated with status error to error notification', async () => {
    const handleEvent = (router as any).handleDashboardEvent.bind(router);
    handleEvent({
      type: 'room_updated',
      data: { room: { room_id: 'room-1', status: 'error' } },
    });
    await new Promise(resolve => setTimeout(resolve, 10));
    expect(mockConnector.sendMessage.firstCall.args[1].text).to.include('System Error');
  });

  it('handles plans_updated (no notification)', async () => {
    const handleEvent = (router as any).handleDashboardEvent.bind(router);
    handleEvent({
      type: 'plans_updated',
      data: {},
    });
    await new Promise(resolve => setTimeout(resolve, 10));
    expect(mockConnector.sendMessage.called).to.be.false;
  });

  it('maps room_removed to plan_completed', async () => {
    const handleEvent = (router as any).handleDashboardEvent.bind(router);
    handleEvent({
      type: 'room_removed',
      data: { room_id: 'room-1' },
    });
    await new Promise(resolve => setTimeout(resolve, 10));
    expect(mockConnector.sendMessage.firstCall.args[1].text).to.include('War-Room Removed');
  });

  it('filters notifications based on preferences', async () => {
    sandbox.restore(); // Clear mocks for this test
    sandbox = sinon.createSandbox();
    
    const mockConnector2 = {
      platform: 'telegram',
      status: 'connected',
      sendMessage: sandbox.stub().resolves(),
    };
    sandbox.stub(registry, 'getConnector').returns(mockConnector2 as any);
    sandbox.stub(registry, 'getAllConfigs').returns([
      {
        platform: 'telegram',
        enabled: true,
        authorized_users: ['u1'],
        notification_preferences: { events: ['epic_failed'], enabled: true }, // Only failures
        credentials: {},
        settings: {},
        pairing_code: '',
      } as any,
    ]);

    const router2 = new NotificationRouter(registry);
    const handleEvent = (router2 as any).handleDashboardEvent.bind(router2);

    // This should be filtered out
    handleEvent({
      type: 'room_updated',
      data: { room: { room_id: 'room-1', status: 'passed' } },
    });

    // This should be delivered
    handleEvent({
      type: 'room_updated',
      data: { room: { room_id: 'room-1', status: 'failed' } },
    });

    await new Promise(resolve => setTimeout(resolve, 10));

    expect(mockConnector2.sendMessage.calledOnce).to.be.true;
    expect(mockConnector2.sendMessage.firstCall.args[1].text).to.include('EPIC Failed');
  });

  it('does not send if global enabled is false', async () => {
    sandbox.restore();
    sandbox = sinon.createSandbox();
    
    const mockConnector3 = {
      platform: 'telegram',
      status: 'connected',
      sendMessage: sandbox.stub().resolves(),
    };
    sandbox.stub(registry, 'getConnector').returns(mockConnector3 as any);
    sandbox.stub(registry, 'getAllConfigs').returns([
      {
        platform: 'telegram',
        enabled: true,
        authorized_users: ['u1'],
        notification_preferences: { events: [], enabled: false }, // Disabled globally
        credentials: {},
        settings: {},
        pairing_code: '',
      } as any,
    ]);

    const router3 = new NotificationRouter(registry);
    const handleEvent = (router3 as any).handleDashboardEvent.bind(router3);

    handleEvent({
      type: 'room_created',
      data: { room: { room_id: 'room-1' } },
    });

    await new Promise(resolve => setTimeout(resolve, 10));
    expect(mockConnector3.sendMessage.called).to.be.false;
  });
});
