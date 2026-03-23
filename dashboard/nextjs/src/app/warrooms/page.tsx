'use client';

import { useState, useCallback } from 'react';
import { useApp } from '@/contexts/AppContext';

import PipelineBar from '@/components/layout/PipelineBar';
import PlanLauncher from '@/components/panels/PlanLauncher';
import WarRoomGrid from '@/components/panels/WarRoomGrid';
import ChannelFeed from '@/components/panels/ChannelFeed';

export default function WarRoomsPage() {
  const {
    rooms,
    roomList,
    summary,
    feedMessages,
    channelFilter,
    activePlanId,
    selectRoom,
    clearFeed,
    loadPlanRooms,
  } = useApp();

  const [leftCollapsed, setLeftCollapsed] = useState(false);
  const [rightCollapsed, setRightCollapsed] = useState(false);
  const [leftWidth, setLeftWidth] = useState(220);
  const [rightWidth, setRightWidth] = useState(380);

  const onLeftDragStart = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      const startX = e.clientX;
      const capturedStartW = leftWidth;
      document.body.style.cursor = 'col-resize';
      document.body.style.userSelect = 'none';
      const onMove = (ev: MouseEvent) => {
        const delta = ev.clientX - startX;
        const newW = Math.max(48, Math.min(480, capturedStartW + delta));
        setLeftWidth(newW);
        setLeftCollapsed(newW <= 48);
      };
      const onUp = () => {
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
        window.removeEventListener('mousemove', onMove);
        window.removeEventListener('mouseup', onUp);
      };
      window.addEventListener('mousemove', onMove);
      window.addEventListener('mouseup', onUp);
    },
    [leftWidth],
  );

  const onRightDragStart = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      const startX = e.clientX;
      const capturedStartW = rightWidth;
      document.body.style.cursor = 'col-resize';
      document.body.style.userSelect = 'none';
      const onMove = (ev: MouseEvent) => {
        const delta = startX - ev.clientX;
        const newW = Math.max(48, Math.min(700, capturedStartW + delta));
        setRightWidth(newW);
        setRightCollapsed(newW <= 48);
      };
      const onUp = () => {
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
        window.removeEventListener('mousemove', onMove);
        window.removeEventListener('mouseup', onUp);
      };
      window.addEventListener('mousemove', onMove);
      window.addEventListener('mouseup', onUp);
    },
    [rightWidth],
  );

  const selectedRoom = channelFilter ? rooms[channelFilter] || null : null;

  return (
    <div className="warrooms-page">
      <PipelineBar rooms={roomList} />

      <div className="warrooms-layout">
        <PlanLauncher
          onPlanSelected={loadPlanRooms}
          isCollapsed={leftCollapsed}
          onToggleCollapse={() => {
            if (leftCollapsed) {
              setLeftCollapsed(false);
              setLeftWidth(220);
            } else {
              setLeftCollapsed(true);
              setLeftWidth(48);
            }
          }}
          style={{ width: leftCollapsed ? 48 : leftWidth, flexShrink: 0 }}
        />

        <div
          className="resize-handle resize-handle-left"
          onMouseDown={onLeftDragStart}
          title="Drag to resize"
        />

        <WarRoomGrid
          rooms={roomList}
          summary={summary}
          channelFilter={channelFilter}
          onSelectRoom={selectRoom}
          style={{ flex: 1, minWidth: 0, overflow: 'hidden' }}
        />

        <div
          className="resize-handle resize-handle-right"
          onMouseDown={onRightDragStart}
          title="Drag to resize"
        />

        <ChannelFeed
          feedMessages={feedMessages}
          channelFilter={channelFilter}
          selectedRoom={selectedRoom}
          activePlanId={activePlanId}
          onClearFeed={clearFeed}
          isCollapsed={rightCollapsed}
          onToggleCollapse={() => {
            if (rightCollapsed) {
              setRightCollapsed(false);
              setRightWidth(380);
            } else {
              setRightCollapsed(true);
              setRightWidth(48);
            }
          }}
          style={{ width: rightCollapsed ? 48 : rightWidth, flexShrink: 0 }}
        />
      </div>
    </div>
  );
}
