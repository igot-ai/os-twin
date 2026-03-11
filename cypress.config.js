const { defineConfig } = require('cypress');
const path = require('path');

module.exports = defineConfig({
  e2e: {
    baseUrl: 'http://localhost:8000',

    // How long to wait for assertions / network (ms)
    defaultCommandTimeout: 8000,
    requestTimeout: 10000,
    responseTimeout: 10000,

    // Viewport matches our desktop preset
    viewportWidth: 1280,
    viewportHeight: 800,

    // Don't fail on uncaught exceptions from the app during SSE
    experimentalRunAllSpecs: true,

    setupNodeEvents(on, config) {
      const AGENTS_DIR = path.join(__dirname, '.agents');
      const WARROOMS  = path.join(AGENTS_DIR, 'war-rooms');

      on('task', {
        // Post a JSONL message to a war-room channel
        postMessage({ room, from_, to, type, ref, body }) {
          const { execSync } = require('child_process');
          const roomPath = path.join(WARROOMS, room);
          execSync(
            `${path.join(AGENTS_DIR, 'channel/post.sh')} "${roomPath}" "${from_}" "${to}" "${type}" "${ref}" "${body.replace(/"/g, '\\"')}"`,
            { cwd: __dirname }
          );
          return null;
        },

        // Write a status file directly
        setRoomStatus({ room, status }) {
          const fs = require('fs');
          fs.writeFileSync(path.join(WARROOMS, room, 'status'), status);
          return null;
        },

        // Read a room status file
        getRoomStatus({ room }) {
          const fs = require('fs');
          try {
            return fs.readFileSync(path.join(WARROOMS, room, 'status'), 'utf8').trim();
          } catch { return null; }
        },

        // Check whether RELEASE.md exists
        releaseExists() {
          const fs = require('fs');
          return fs.existsSync(path.join(AGENTS_DIR, 'RELEASE.md'));
        },

        // List existing room IDs
        listRooms() {
          const fs = require('fs');
          try {
            return fs.readdirSync(WARROOMS)
              .filter(d => /^room-\d+$/.test(d))
              .sort();
          } catch { return []; }
        },

        // Kill the running manager (if any) and clean up rooms + release artifacts
        resetAgentOS() {
          const { execSync } = require('child_process');
          const fs = require('fs');

          // Kill manager
          const pidFile = path.join(AGENTS_DIR, 'manager.pid');
          if (fs.existsSync(pidFile)) {
            const pid = fs.readFileSync(pidFile, 'utf8').trim();
            try { execSync(`kill -9 ${pid} 2>/dev/null || true`); } catch {}
            fs.unlinkSync(pidFile);
          }

          // Remove war-rooms
          const rooms = fs.readdirSync(WARROOMS).filter(d => /^room-/.test(d));
          for (const room of rooms) {
            try {
              execSync(
                `${path.join(WARROOMS, 'teardown.sh')} ${room} --force 2>/dev/null || true`,
                { cwd: __dirname }
              );
            } catch {}
          }

          // Remove release artifacts
          ['RELEASE.md', 'release/signoffs.json'].forEach(f => {
            try { fs.unlinkSync(path.join(AGENTS_DIR, f)); } catch {}
          });

          return null;
        },
      });
    },
  },
});
