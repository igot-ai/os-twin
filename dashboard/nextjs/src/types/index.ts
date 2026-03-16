// === Room Config (from room's config.json) ===
export interface RoomConfig {
  plan_id?: string;
  task_ref?: string;
  epic_ref?: string;
  [key: string]: unknown;
}

// === Role Instance (from *_*.json files in room dir) ===
export interface RoleInstance {
  role: string;
  instance_id: string;
  filename?: string;
  status?: string;
  [key: string]: unknown;
}

// === Room ===
export interface Room {
  room_id: string;
  task_ref: string;
  status: RoomStatus;
  retries: number;
  message_count: number;
  last_activity: string | null;
  task_description: string | null;
  goal_total: number;
  goal_done: number;
  // Extended metadata (present when fetched with include_metadata)
  config?: RoomConfig;
  roles?: RoleInstance[];
  state_changed_at?: string | null;
  artifact_files?: string[];
  audit_tail?: string[];
  working_dir?: string;
}

export type RoomStatus =
  | 'pending'
  | 'engineering'
  | 'qa-review'
  | 'fixing'
  | 'passed'
  | 'failed-final'
  | 'paused';

// === Message ===
export interface Message {
  id?: string;
  ts: string;
  from_?: string;
  from?: string;
  to: string;
  type: MessageType;
  ref: string;
  body: string;
}

export type MessageType =
  | 'task'
  | 'done'
  | 'review'
  | 'pass'
  | 'fail'
  | 'fix'
  | 'signoff'
  | 'release'
  | 'error';

// === Plan ===
export interface Plan {
  plan_id: string;
  title: string;
  content: string;
  status: string;
  epic_count: number;
  created_at: string;
  filename: string;
}

// === Epic ===
export interface Epic {
  epic_ref: string;
  plan_id: string;
  title: string;
  body?: string;
  room_id: string;
  working_dir?: string;
  status: string;
}

// === Config ===
export interface ManagerConfig {
  max_concurrent_rooms?: number;
  poll_interval_seconds?: number;
  max_engineer_retries?: number;
}

// === Notification ===
export interface Notification {
  v: number;
  id: string;
  ts: string;
  from: string;
  to: string;
  type: string;
  ref: string;
  body: string;
}

// === WebSocket Event ===
export interface WSEvent {
  event: string;
  room?: Room;
  room_id?: string;
  new_messages?: Message[];
  content?: string;
  entity_id?: string;
  state?: Record<string, unknown>;
  comment?: Record<string, unknown>;
  [key: string]: unknown;
}

// === Directory Browser ===
export interface DirEntry {
  name: string;
  path: string;
  has_children: boolean;
}

export interface BrowseResult {
  current: string;
  parent: string | null;
  dirs: DirEntry[];
}

// === Search ===
export interface SearchResult {
  room_id: string;
  type: string;
  ref: string;
  body: string;
  score: number;
}
