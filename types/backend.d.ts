/**
 * TypeScript interfaces for the Task Management System backend.
 *
 * These types mirror the JSON shapes returned by the REST API and
 * the payloads pushed through WebSocket events.
 */

// ═══════════════════════════════════════════════════════
//  Enums
// ═══════════════════════════════════════════════════════

export type UserRole = "ADMIN" | "PM" | "DEVELOPER" | "DESIGNER";

export type ProjectStatus = "ACTIVE" | "ARCHIVED" | "COMPLETED";

export type TaskStatus = "TODO" | "IN_PROGRESS" | "REVIEW" | "DONE";

export type TaskPriority = "LOW" | "MEDIUM" | "HIGH" | "URGENT";

// ═══════════════════════════════════════════════════════
//  API Response Types
// ═══════════════════════════════════════════════════════

export interface IUser {
  id: number;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  role: UserRole;
  avatar: string;
  date_joined: string; // ISO 8601
}

export interface IProject {
  id: number;
  name: string;
  description: string;
  status: ProjectStatus;
  owner: IUser;
  members: IUser[];
  task_count: number;
  created_at: string; // ISO 8601
  updated_at: string; // ISO 8601
}

export interface ITask {
  id: number;
  title: string;
  description: string;
  status: TaskStatus;
  priority: TaskPriority;
  is_approved: boolean;
  due_date: string | null; // YYYY-MM-DD
  project: number;
  assignee: IUser | null;
  created_by: IUser;
  created_at: string; // ISO 8601
  updated_at: string; // ISO 8601
}

export interface IChannel {
  id: number;
  name: string;
  project: number;
  members: IUser[];
  created_at: string; // ISO 8601
}

export interface IMessage {
  id: number;
  content: string;
  channel: number;
  sender: IUser;
  timestamp: string; // ISO 8601
}

export interface IFeedback {
  id: number;
  content: string;
  rating: number; // 1–5
  project: number;
  created_at: string; // ISO 8601
}

export interface IDashboard {
  total_tasks: number;
  completed_tasks: number;
  in_progress_tasks: number;
  review_tasks: number;
  todo_tasks: number;
  approved_tasks: number;
  progress_percentage: number; // 0–100
  tasks_by_priority: Record<TaskPriority, number>;
  recent_tasks: ITask[];
}

// ═══════════════════════════════════════════════════════
//  Paginated Response Wrapper
// ═══════════════════════════════════════════════════════

export interface IPaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

// ═══════════════════════════════════════════════════════
//  Auth Request / Response Types
// ═══════════════════════════════════════════════════════

export interface ILoginRequest {
  username: string;
  password: string;
}

export interface IRegisterRequest {
  username: string;
  email: string;
  password: string;
  password_confirm: string;
  first_name?: string;
  last_name?: string;
  role?: UserRole;
}

export interface IUserUpdateRequest {
  first_name?: string;
  last_name?: string;
  email?: string;
  role?: UserRole;
  avatar?: string;
}

// ═══════════════════════════════════════════════════════
//  Action Request Types
// ═══════════════════════════════════════════════════════

export interface ITaskMoveRequest {
  status: TaskStatus;
}

export interface ITaskApproveRequest {
  is_approved: boolean;
}

export interface IProjectMemberRequest {
  user_ids: number[];
}

// ═══════════════════════════════════════════════════════
//  WebSocket Event Types
// ═══════════════════════════════════════════════════════

export interface IWebSocketMessage<T = unknown> {
  event: string;
  data: T;
}

/** Broadcast when a task's Kanban column (status) changes. */
export interface ITaskMovedEvent {
  task_id: number;
  title: string;
  old_status: TaskStatus;
  new_status: TaskStatus;
  moved_by: number | null; // user id
  project_id: number;
}

/** Broadcast when a task is approved or assigned. */
export interface INotificationEvent {
  notification_type: "task_approved" | "task_assigned";
  message: string;
  task_id: number;
  target_user: number | null; // user id
  project_id: number;
}

/** Broadcast when a new chat message is sent. */
export interface INewMessageEvent {
  message_id: number;
  content: string;
  sender: {
    id: number;
    username: string;
    avatar: string;
  };
  channel_id: number;
  timestamp: string; // ISO 8601
}

// ═══════════════════════════════════════════════════════
//  WebSocket URL Patterns
// ═══════════════════════════════════════════════════════
//
//  Project events:  ws://<host>/ws/project/<project_id>/
//  Chat messages:   ws://<host>/ws/chat/<channel_id>/
//
