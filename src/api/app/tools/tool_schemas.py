"""JSON-schema-style tool definitions for Azure AI Foundry agents.

Each schema follows the OpenAI function-calling format consumed by the
Foundry agents SDK: ``{"type": "function", "function": {...}}``.

The v2 ``AGENT_TOOLS_V2`` mapping provides FunctionTool model objects
for ``PromptAgentDefinition.tools`` (``agents.create_version()``).
"""

from azure.ai.projects.models import FunctionTool

# ── Individual tool schemas ─────────────────────────────────────────

GET_PATIENT = {
    "type": "function",
    "function": {
        "name": "get_patient",
        "description": "Look up a single patient by their unique ID. Returns patient demographics, state, location, acuity, and assigned bed.",
        "parameters": {
            "type": "object",
            "properties": {
                "patient_id": {"type": "string", "description": "The unique patient identifier (e.g. P-001)."},
            },
            "required": ["patient_id"],
        },
    },
}

GET_BEDS = {
    "type": "function",
    "function": {
        "name": "get_beds",
        "description": "List hospital beds, optionally filtered by unit, state, and/or diagnosis. When diagnosis is provided, only beds on clinically appropriate units are returned (e.g., cardiac patients only see Cardiac/Telemetry beds).",
        "parameters": {
            "type": "object",
            "properties": {
                "unit": {"type": "string", "description": "Filter by nursing unit (e.g. '4-North'). Omit to return all units."},
                "state": {"type": "string", "description": "Filter by bed state (OCCUPIED, RESERVED, DIRTY, CLEANING, READY, BLOCKED). Omit to return all states."},
                "diagnosis": {"type": "string", "description": "Patient diagnosis or admission reason. When provided, filters beds to clinically appropriate units only (e.g., 'chest pain' returns only Cardiac/Telemetry beds)."},
            },
            "required": [],
        },
    },
}

GET_TASKS = {
    "type": "function",
    "function": {
        "name": "get_tasks",
        "description": "List tasks, optionally filtered by state and/or type. Returns task ID, type, subject, state, priority.",
        "parameters": {
            "type": "object",
            "properties": {
                "task_state": {"type": "string", "description": "Filter by task state (CREATED, ACCEPTED, IN_PROGRESS, COMPLETED, ESCALATED, CANCELLED)."},
                "task_type": {"type": "string", "description": "Filter by task type (EVS_CLEANING, TRANSPORT, BED_PREP, OTHER)."},
            },
            "required": [],
        },
    },
}

RESERVE_BED = {
    "type": "function",
    "function": {
        "name": "reserve_bed",
        "description": "Reserve a specific bed for a patient. Transitions bed to RESERVED state, creates a reservation with a hold timer. Only works on READY beds.",
        "parameters": {
            "type": "object",
            "properties": {
                "bed_id": {"type": "string", "description": "The bed to reserve (e.g. BED-401B)."},
                "patient_id": {"type": "string", "description": "The patient to reserve the bed for."},
                "hold_minutes": {"type": "integer", "description": "How long to hold the reservation in minutes. Default 30.", "default": 30},
            },
            "required": ["bed_id", "patient_id"],
        },
    },
}

RELEASE_BED_RESERVATION = {
    "type": "function",
    "function": {
        "name": "release_bed_reservation",
        "description": "Release a bed reservation, transitioning the bed back to READY. Deactivates any active reservations on this bed.",
        "parameters": {
            "type": "object",
            "properties": {
                "bed_id": {"type": "string", "description": "The bed whose reservation to release."},
            },
            "required": ["bed_id"],
        },
    },
}

CREATE_TASK = {
    "type": "function",
    "function": {
        "name": "create_task",
        "description": "Create a new task (e.g. EVS cleaning, bed prep). The task starts in CREATED state.",
        "parameters": {
            "type": "object",
            "properties": {
                "task_type": {"type": "string", "enum": ["EVS_CLEANING", "TRANSPORT", "BED_PREP", "OTHER"], "description": "The type of task to create."},
                "subject_id": {"type": "string", "description": "The entity this task is about (e.g. a bed ID)."},
                "priority": {"type": "string", "enum": ["STAT", "URGENT", "ROUTINE"], "description": "Task priority. Default ROUTINE.", "default": "ROUTINE"},
                "due_by": {"type": "string", "description": "ISO 8601 datetime for when the task must be completed. Optional."},
                "notes": {"type": "string", "description": "Free-text notes about the task."},
            },
            "required": ["task_type", "subject_id"],
        },
    },
}

UPDATE_TASK = {
    "type": "function",
    "function": {
        "name": "update_task",
        "description": "Update a task's status and/or ETA. Transitions must follow the task state machine.",
        "parameters": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "The task to update."},
                "new_status": {"type": "string", "enum": ["ACCEPTED", "IN_PROGRESS", "COMPLETED", "ESCALATED", "CANCELLED"], "description": "The new task state."},
                "eta_minutes": {"type": "integer", "description": "Updated estimated time to completion in minutes."},
            },
            "required": ["task_id", "new_status"],
        },
    },
}

SCHEDULE_TRANSPORT = {
    "type": "function",
    "function": {
        "name": "schedule_transport",
        "description": "Schedule a patient transport between two locations. Creates a transport record in CREATED state.",
        "parameters": {
            "type": "object",
            "properties": {
                "patient_id": {"type": "string", "description": "The patient being transported."},
                "from_location": {"type": "string", "description": "Pickup location (e.g. 'ED Bay 3')."},
                "to_location": {"type": "string", "description": "Destination (e.g. '4-North 401B')."},
                "priority": {"type": "string", "enum": ["STAT", "URGENT", "ROUTINE"], "description": "Transport priority. Default ROUTINE.", "default": "ROUTINE"},
                "earliest_time": {"type": "string", "description": "ISO 8601 earliest departure time. Optional."},
            },
            "required": ["patient_id", "from_location", "to_location"],
        },
    },
}

PUBLISH_EVENT = {
    "type": "function",
    "function": {
        "name": "publish_event",
        "description": "Emit a generic event to the event stream. Use for events not covered by specific tools.",
        "parameters": {
            "type": "object",
            "properties": {
                "event_type": {"type": "string", "description": "The event type string."},
                "entity_id": {"type": "string", "description": "The entity this event pertains to."},
                "payload": {"type": "object", "description": "Arbitrary event payload data."},
            },
            "required": ["event_type", "entity_id"],
        },
    },
}

ESCALATE = {
    "type": "function",
    "function": {
        "name": "escalate",
        "description": "Escalate an issue by emitting an SlaRiskDetected event. Use when SLA thresholds are at risk or safety concerns arise.",
        "parameters": {
            "type": "object",
            "properties": {
                "issue_type": {"type": "string", "description": "Category of issue (e.g. 'sla_breach', 'safety_concern', 'capacity_overflow')."},
                "entity_id": {"type": "string", "description": "The entity involved in the escalation."},
                "severity": {"type": "string", "enum": ["LOW", "MEDIUM", "HIGH", "CRITICAL"], "description": "Severity level."},
                "message": {"type": "string", "description": "Human-readable description of the issue."},
            },
            "required": ["issue_type", "entity_id", "severity", "message"],
        },
    },
}


# ── Per-agent tool sets ─────────────────────────────────────────────

FLOW_COORDINATOR_TOOLS = [GET_PATIENT, GET_BEDS, GET_TASKS, PUBLISH_EVENT, ESCALATE]
PREDICTIVE_CAPACITY_TOOLS = [GET_BEDS, GET_TASKS, GET_PATIENT, PUBLISH_EVENT]
BED_ALLOCATION_TOOLS = [GET_BEDS, GET_PATIENT, RESERVE_BED, RELEASE_BED_RESERVATION, PUBLISH_EVENT]
EVS_TASKING_TOOLS = [GET_BEDS, GET_TASKS, CREATE_TASK, UPDATE_TASK, PUBLISH_EVENT]
TRANSPORT_OPS_TOOLS = [GET_PATIENT, GET_TASKS, SCHEDULE_TRANSPORT, PUBLISH_EVENT]
POLICY_SAFETY_TOOLS = [GET_PATIENT, GET_BEDS, GET_TASKS, ESCALATE, PUBLISH_EVENT]

AGENT_TOOLS: dict[str, list[dict]] = {
    "bed-coordinator": FLOW_COORDINATOR_TOOLS,
    "predictive-capacity": PREDICTIVE_CAPACITY_TOOLS,
    "bed-allocation": BED_ALLOCATION_TOOLS,
    "evs-tasking": EVS_TASKING_TOOLS,
    "transport-ops": TRANSPORT_OPS_TOOLS,
    "policy-safety": POLICY_SAFETY_TOOLS,
}


# ── v2 FunctionTool objects (for PromptAgentDefinition.tools) ───────

def _to_function_tool(schema: dict) -> FunctionTool:
    """Convert a legacy dict schema to a FunctionTool model object."""
    fn = schema["function"]
    return FunctionTool(
        name=fn["name"],
        description=fn["description"],
        parameters=fn.get("parameters", {}),
    )


AGENT_TOOLS_V2: dict[str, list[FunctionTool]] = {
    agent_name: [_to_function_tool(s) for s in tools]
    for agent_name, tools in AGENT_TOOLS.items()
}
