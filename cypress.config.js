const { defineConfig } = require('cypress')
const fs = require('fs')
const path = require('path')

module.exports = defineConfig({
  e2e: {
    baseUrl: 'http://127.0.0.1:4444',
    defaultCommandTimeout: 10000,
    requestTimeout: 10000,
    responseTimeout: 10000,
    pageLoadTimeout: 30000,
    setupNodeEvents(on) {
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
        },

        /**
         * Create a test plan with working_dir and war-room directories.
         * Options: { planId, workingDir, rooms: [{ roomId, taskRef, status }] }
         * Returns: { planId, workingDir, warRoomsDir }
         */
        createTestPlan({ planId, workingDir, planContent, rooms }) {
          try {
            const agentsDir = path.resolve(__dirname, '.agents');
            const plansDir = path.join(agentsDir, 'plans');
            if (!fs.existsSync(plansDir)) fs.mkdirSync(plansDir, { recursive: true });

            // Write plan .md file
            const planFile = path.join(plansDir, `${planId}.md`);
            const content = planContent || `# Plan: Cypress War-Room Test\n\n## Config\nworking_dir: ${workingDir}\n\n## Epic: EPIC-001 — Test Epic\n\nTest description.\n`;
            fs.writeFileSync(planFile, content, 'utf8');

            // Write meta.json
            const metaFile = path.join(plansDir, `${planId}.meta.json`);
            const meta = {
              plan_id: planId,
              title: 'Cypress War-Room Test',
              status: 'launched',
              created_at: new Date().toISOString(),
              working_dir: workingDir,
              warrooms_dir: path.join(workingDir, '.war-rooms')
            };
            fs.writeFileSync(metaFile, JSON.stringify(meta, null, 2), 'utf8');

            // Create war-room directories
            const warRoomsDir = path.join(workingDir, '.war-rooms');
            if (!fs.existsSync(warRoomsDir)) fs.mkdirSync(warRoomsDir, { recursive: true });

            for (const room of (rooms || [])) {
              const roomDir = path.join(warRoomsDir, room.roomId);
              if (!fs.existsSync(roomDir)) fs.mkdirSync(roomDir, { recursive: true });

              // Write status file
              fs.writeFileSync(path.join(roomDir, 'status'), room.status || 'pending', 'utf8');

              // Write task-ref file (read_room reads from this file, not config.json)
              fs.writeFileSync(path.join(roomDir, 'task-ref'), room.taskRef || room.roomId, 'utf8');

              // Write TASKS.md with goal checklist
              const tasksContent = `# ${room.taskRef || room.roomId} — ${room.description || 'Test task'}\n\n- [ ] Implementation complete\n- [ ] Tests passing\n- [ ] Code reviewed\n`;
              fs.writeFileSync(path.join(roomDir, 'TASKS.md'), tasksContent, 'utf8');

              // Write config.json with task ref
              const roomConfig = {
                plan_id: planId,
                task_ref: room.taskRef || room.roomId,
                description: room.description || `Task for ${room.roomId}`
              };
              fs.writeFileSync(path.join(roomDir, 'config.json'), JSON.stringify(roomConfig, null, 2), 'utf8');

              // Write initial channel message
              const channelFile = path.join(roomDir, 'channel.jsonl');
              const msg = {
                id: `msg-init-${Date.now()}`,
                ts: new Date().toISOString(),
                from_: 'manager',
                to: 'engineer',
                type: 'task',
                ref: room.taskRef || room.roomId,
                body: `Initialize ${room.roomId}: ${room.description || 'test task'}`,
                payload: {}
              };
              fs.writeFileSync(channelFile, JSON.stringify(msg) + '\n', 'utf8');
            }

            return { planId, workingDir, warRoomsDir };
          } catch (e) {
            console.error('Error in createTestPlan', e);
            return null;
          }
        },

        /**
         * Clean up a test plan and its war-rooms.
         * Options: { planId, workingDir }
         */
        cleanupTestPlan({ planId, workingDir }) {
          try {
            const agentsDir = path.resolve(__dirname, '.agents');
            const plansDir = path.join(agentsDir, 'plans');

            // Remove plan files
            for (const ext of ['.md', '.meta.json', '.roles.json']) {
              const file = path.join(plansDir, `${planId}${ext}`);
              if (fs.existsSync(file)) fs.rmSync(file, { force: true });
            }

            // Remove war-rooms directory
            if (workingDir) {
              const warRoomsDir = path.join(workingDir, '.war-rooms');
              if (fs.existsSync(warRoomsDir)) {
                fs.rmSync(warRoomsDir, { recursive: true, force: true });
              }
            }

            return null;
          } catch (e) {
            console.error('Error in cleanupTestPlan', e);
            return null;
          }
        },

        /**
         * Write a notification/activity log entry for a room.
         */
        writeNotification({ room, warRoomsDir, event, data }) {
          try {
            const roomDir = warRoomsDir
              ? path.join(warRoomsDir, room)
              : path.resolve(__dirname, '.war-rooms', room);
            if (!fs.existsSync(roomDir)) fs.mkdirSync(roomDir, { recursive: true });

            const notifFile = path.join(roomDir, 'notifications.jsonl');
            const entry = {
              ts: new Date().toISOString(),
              event: event || 'room_updated',
              data: data || { room: { room_id: room, status: 'pending' } }
            };
            fs.appendFileSync(notifFile, JSON.stringify(entry) + '\n', 'utf8');
            return null;
          } catch (e) {
            console.error('Error in writeNotification', e);
            return null;
          }
        }
      });
    }
  }
})

