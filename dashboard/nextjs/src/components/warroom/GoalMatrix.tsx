'use client';

import { Room } from '@/types';

interface GoalMatrixProps {
  rooms: Room[];
}

export default function GoalMatrix({ rooms }: GoalMatrixProps) {
  if (rooms.length === 0) {
    return (
      <div className="goal-matrix">
        <table className="matrix-table">
          <tbody>
            <tr>
              <td
                colSpan={100}
                style={{ textAlign: 'center', padding: '40px', color: 'var(--text-dim)' }}
              >
                No active rooms
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    );
  }

  // Collect all unique goal names across all rooms
  const allGoals = new Set<string>();
  rooms.forEach((r) => {
    if (r.task_description) {
      const tasks = r.task_description.match(/- \[[ xX\-!]+\] .+/g) || [];
      tasks.forEach((t) => allGoals.add(t.replace(/- \[[ xX\-!]+\] /, '')));
    }
  });

  const goalArray = Array.from(allGoals);

  return (
    <div className="goal-matrix">
      <table className="matrix-table">
        <thead>
          <tr>
            <th>Goal / Room</th>
            {rooms.map((r) => (
              <th key={r.room_id}>{r.room_id}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {goalArray.map((goal) => (
            <tr key={goal}>
              <td style={{ fontWeight: 500 }}>{goal}</td>
              {rooms.map((r) => {
                let statusEl = null;
                if (r.task_description) {
                  const lines = r.task_description.split('\n');
                  const taskLine = lines.find(
                    (line) => line.includes(goal) && line.trim().startsWith('- ['),
                  );
                  if (taskLine) {
                    if (taskLine.includes('[x]') || taskLine.includes('[X]')) {
                      statusEl = <span className="cell-passed">✓</span>;
                    } else if (taskLine.includes('[-]') || taskLine.includes('[!]')) {
                      statusEl = <span className="cell-failed">✗</span>;
                    } else {
                      statusEl = <span className="cell-pending">○</span>;
                    }
                  }
                }
                return (
                  <td key={r.room_id} className="matrix-cell">
                    {statusEl}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
