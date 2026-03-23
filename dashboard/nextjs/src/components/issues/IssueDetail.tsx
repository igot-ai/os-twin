'use client';

import { useState } from 'react';
import { Message, Notification } from '@/types';
import { IssueEpic } from '@/hooks/useIssues';
import { ISSUE_STATUS, getAssignee } from '@/lib/issue-utils';
import { MSG_ICON } from '@/lib/constants';
import { apiGet } from '@/lib/api';
import { fmtTime, trunc } from '@/lib/utils';

type Tab = 'description' | 'activity' | 'checklist';

interface IssueDetailProps {
  issue: IssueEpic;
  onBack: () => void;
}

export default function IssueDetail({ issue, onBack }: IssueDetailProps) {
  const [tab, setTab] = useState<Tab>('description');
  const [messages, setMessages] = useState<Message[]>([]);
  const [messagesLoading, setMessagesLoading] = useState(false);

  const st = ISSUE_STATUS[issue.status];
  const assignee = getAssignee(issue.status);

  function switchTab(t: Tab) {
    setTab(t);
    if (t === 'activity' && messages.length === 0) loadMessages();
  }

  async function loadMessages() {
    if (!issue.room_id || !issue.plan_id) return;
    setMessagesLoading(true);
    try {
      const data = await apiGet<{ messages?: Message[] }>(
        `/api/plans/${issue.plan_id}/rooms/${issue.room_id}/channel`,
      );
      setMessages(data.messages || []);
    } catch {
      try {
        const data = await apiGet<Notification[] | { notifications: Notification[] }>(
          `/api/notifications?plan_id=${issue.plan_id}&room_id=${issue.room_id}&limit=50`,
        );
        const items = Array.isArray(data) ? data : data.notifications || [];
        setMessages(
          items.map((n) => ({
            ts: n.ts,
            from: n.from,
            to: n.to,
            type: n.type as Message['type'],
            ref: n.ref,
            body: n.body,
          })),
        );
      } catch {
        /* no messages */
      }
    } finally {
      setMessagesLoading(false);
    }
  }

  const checklist = parseChecklist(issue.body || '');

  const tabs: { key: Tab; label: string }[] = [
    { key: 'description', label: 'Description' },
    { key: 'activity', label: 'Activity' },
    { key: 'checklist', label: `Checklist (${checklist.length})` },
  ];

  return (
    <div className="issue-detail">
      <button className="breadcrumb-back" onClick={onBack}>
        ← Issues
      </button>

      <div className="issue-detail-header">
        <span className="issue-detail-ref">{issue.epic_ref}</span>
        <h1 className="page-title" style={{ margin: 0 }}>
          {issue.title}
        </h1>
        <div className="issue-detail-meta">
          <span className="issue-detail-badge" style={{ color: st?.color }}>
            {st?.icon} {st?.label}
          </span>
          {assignee && <span className="issue-detail-assignee">{assignee}</span>}
          <span className="issue-detail-plan">Plan: {issue.plan_title}</span>
          {issue.room_id && <span className="issue-detail-room">Room: {issue.room_id}</span>}
        </div>
      </div>

      <div className="tab-bar">
        {tabs.map((t) => (
          <button
            key={t.key}
            className={`tab-btn${tab === t.key ? ' active' : ''}`}
            onClick={() => switchTab(t.key)}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="tab-content">
        {tab === 'description' && <DescriptionTab body={issue.body} />}
        {tab === 'activity' && <ActivityTab messages={messages} loading={messagesLoading} />}
        {tab === 'checklist' && <ChecklistTab items={checklist} />}
      </div>
    </div>
  );
}

function DescriptionTab({ body }: { body?: string }) {
  if (!body) {
    return (
      <div className="empty-state">
        <p>No description available.</p>
      </div>
    );
  }

  return (
    <div className="issue-body">
      <pre className="issue-body-text">{body}</pre>
    </div>
  );
}

function ActivityTab({ messages, loading }: { messages: Message[]; loading: boolean }) {
  if (loading) {
    return (
      <div className="empty-state">
        <p>Loading activity...</p>
      </div>
    );
  }

  if (messages.length === 0) {
    return (
      <div className="empty-state">
        <p>No activity yet.</p>
      </div>
    );
  }

  return (
    <div className="issue-activity">
      {messages.map((msg, i) => {
        const from = msg.from_ || msg.from || '?';
        return (
          <div key={i} className={`activity-msg activity-${msg.type || 'unknown'}`}>
            <span className="activity-time">{fmtTime(msg.ts)}</span>
            <span className="activity-route">
              {from}→{msg.to}
            </span>
            <span className="activity-type">
              {MSG_ICON[msg.type] || '·'} {msg.type}
            </span>
            <span className="activity-body">{trunc(msg.body || '', 120)}</span>
          </div>
        );
      })}
    </div>
  );
}

function ChecklistTab({ items }: { items: ChecklistItem[] }) {
  if (items.length === 0) {
    return (
      <div className="empty-state">
        <p>No checklist items found in the epic body.</p>
      </div>
    );
  }

  return (
    <div className="issue-checklist">
      {items.map((item, i) => (
        <div key={i} className={`checklist-item${item.checked ? ' checked' : ''}`}>
          <span className="checklist-check">{item.checked ? '☑' : '☐'}</span>
          <span className="checklist-text">{item.text}</span>
        </div>
      ))}
    </div>
  );
}

interface ChecklistItem {
  text: string;
  checked: boolean;
}

function parseChecklist(body: string): ChecklistItem[] {
  const items: ChecklistItem[] = [];
  const lines = body.split('\n');
  for (const line of lines) {
    const trimmed = line.trim();
    if (trimmed.startsWith('- [x]') || trimmed.startsWith('- [X]')) {
      items.push({ text: trimmed.slice(5).trim(), checked: true });
    } else if (trimmed.startsWith('- [ ]')) {
      items.push({ text: trimmed.slice(5).trim(), checked: false });
    } else if (trimmed.startsWith('- ')) {
      const text = trimmed.slice(2).trim();
      if (text) items.push({ text, checked: false });
    }
  }
  return items;
}
