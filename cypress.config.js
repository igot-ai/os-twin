const { defineConfig } = require('cypress')
const fs = require('fs')
const path = require('path')

module.exports = defineConfig({
  e2e: {
    baseUrl: 'http://localhost:3000',
    setupNodeEvents(on, config) {
      on('task', {
        resetAgentOS() {
          try {
            const warRoomsDir = path.resolve(__dirname, '.war-rooms');
            if (fs.existsSync(warRoomsDir)) {
              fs.rmSync(warRoomsDir, { recursive: true, force: true });
            }
            const agentsDir = path.resolve(__dirname, '.agents');
            const managerPidFile = path.join(agentsDir, 'manager.pid');
            if (fs.existsSync(managerPidFile)) {
              fs.rmSync(managerPidFile, { force: true });
            }
            // add a small delay
            return new Promise(resolve => setTimeout(() => resolve(null), 200));
          } catch (e) {
            console.error('Error in resetAgentOS', e);
            return null;
          }
        },
        setRoomStatus({ room, status }) {
          const roomDir = path.resolve(__dirname, '.war-rooms', room);
          if (!fs.existsSync(roomDir)) fs.mkdirSync(roomDir, { recursive: true });
          const statusFile = path.join(roomDir, 'status');
          fs.writeFileSync(statusFile, status, 'utf8');
          return null;
        },
        postMessage({ room, from_, to, type, ref, body }) {
          const roomDir = path.resolve(__dirname, '.war-rooms', room);
          if (!fs.existsSync(roomDir)) fs.mkdirSync(roomDir, { recursive: true });
          const channelFile = path.join(roomDir, 'channel.jsonl');
          const msg = {
            id: `msg-${Date.now()}`,
            ts: new Date().toISOString(),
            from_: from_ || 'system',
            to: to || 'all',
            type: type || 'text',
            ref: ref || '',
            body: body || '',
            payload: {}
          };
          fs.appendFileSync(channelFile, JSON.stringify(msg) + '\n', 'utf8');
          return null;
        }
      });
    }
  }
})
