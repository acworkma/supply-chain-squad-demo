// ── State enums as string unions ────────────────────────────────

export type BedState =
  | "OCCUPIED"
  | "RESERVED"
  | "DIRTY"
  | "CLEANING"
  | "READY"
  | "BLOCKED";

export type PatientState =
  | "AWAITING_BED"
  | "BED_ASSIGNED"
  | "TRANSPORT_READY"
  | "IN_TRANSIT"
  | "ARRIVED"
  | "DISCHARGED";

export type TaskState =
  | "CREATED"
  | "ACCEPTED"
  | "IN_PROGRESS"
  | "COMPLETED"
  | "ESCALATED"
  | "CANCELLED";

export type TaskType = "EVS_CLEANING" | "TRANSPORT" | "BED_PREP" | "OTHER";

export type TransportPriority = "STAT" | "URGENT" | "ROUTINE";

export type IntentTag = "PROPOSE" | "VALIDATE" | "EXECUTE" | "ESCALATE";

export type AdmissionSource = "ER" | "OR" | "DIRECT_ADMIT" | "TRANSFER";

// ── Entity interfaces ──────────────────────────────────────────

export interface Bed {
  id: string;
  unit: string;
  room_number: string;
  bed_letter: string;
  state: BedState;
  patient_id: string | null;
  reserved_for_patient_id: string | null;
  reserved_until: string | null;
  last_state_change: string;
}

export interface Patient {
  id: string;
  name: string;
  mrn: string;
  state: PatientState;
  current_location: string;
  assigned_bed_id: string | null;
  diagnosis: string;
  acuity_level: number;
  admission_source: AdmissionSource;
  requested_at: string;
  eta_minutes: number | null;
}

export interface Task {
  id: string;
  type: TaskType;
  subject_id: string;
  state: TaskState;
  priority: TransportPriority;
  assigned_to: string | null;
  created_at: string;
  accepted_at: string | null;
  completed_at: string | null;
  due_by: string | null;
  notes: string;
  eta_minutes: number | null;
}

export interface Transport {
  id: string;
  patient_id: string;
  from_location: string;
  to_location: string;
  priority: TransportPriority;
  state: TaskState;
  scheduled_time: string | null;
  started_at: string | null;
  completed_at: string | null;
  assigned_to: string | null;
}

export interface Reservation {
  id: string;
  bed_id: string;
  patient_id: string;
  created_at: string;
  hold_until: string;
  is_active: boolean;
}

export interface StateDiff {
  from_state: string;
  to_state: string;
}

export interface Event {
  id: string;
  sequence: number;
  timestamp: string;
  event_type: string;
  entity_id: string;
  payload: Record<string, unknown>;
  state_diff: StateDiff | null;
}

export interface AgentMessage {
  id: string;
  timestamp: string;
  agent_name: string;
  agent_role: string;
  content: string;
  intent_tag: IntentTag;
  related_event_ids: string[];
}

// ── Hospital configuration types ───────────────────────────────

export interface CampusConfig {
  id: string;
  name: string;
  has_dedicated_transporters: boolean;
}

export interface UnitConfig {
  id: string;
  name: string;
  campus_id: string;
  specialty: string;
  allowed_diagnoses: string[];
}

export interface HospitalConfig {
  campuses: Record<string, CampusConfig>;
  units: Record<string, UnitConfig>;
}

// ── API response shapes ────────────────────────────────────────

export interface StateResponse {
  beds: Record<string, Bed>;
  patients: Record<string, Patient>;
  tasks: Record<string, Task>;
  transports: Record<string, Transport>;
  reservations: Record<string, Reservation>;
  hospital_config: HospitalConfig;
}
