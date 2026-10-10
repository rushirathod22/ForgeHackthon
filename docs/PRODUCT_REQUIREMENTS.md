# ASK MY CCTV — Product Requirements Document (PRD)

**Document Version**: 1.0.0  
**Date**: August 24, 2026  

---

## 1. Product Vision

**ASK MY CCTV** is an AI-powered CCTV video intelligence operating system that transforms traditional physical security monitoring into a natural, conversational experience. Security operators, facility managers, and investigators interact with an entire network of CCTV cameras by speaking or typing naturally. The system understands requests, searches across camera feeds, reconstructs target movement journeys, extracts evidence, and dispatches security officers.

---

## 2. Target Users & Use Cases

### Primary User Persona: Security Operations Center (SOC) Specialist
- **Need**: Rapidly find specific incidents across dozens of camera feeds without manually scrubbing through hours of footage.
- **Key Use Case**: *"Find people wearing helmets near the main gate after 9 PM."*

### Secondary User Persona: Facility Manager / Security Supervisor
- **Need**: Track suspicious individuals or unauthorized intruders across multiple building zones and share evidence with response teams.
- **Key Use Case**: *"Where did this person go next?"* ➔ Spatial multi-camera story reconstruction ➔ *"Call security and explain what happened."*

---

## 3. Core Product Experience & User Flows

```
[ USER INPUT ]
Natural Voice or Text Query (e.g. "Find people wearing helmets near main gate")
       │
       ▼
[ AI CONCEPT EXTRACTION ]
ASK AI extracts concepts: [PERSON] [HELMET] [MAIN GATE] [10:42 AM]
       │
       ▼
[ CAMERA UNIVERSE SEARCH ]
Organic node-graph visualization activates. Signals stream to nodes.
Nodes scan & report: SCANNING ➔ POSSIBLE MATCH ➔ ✦ MATCH FOUND (CAM_04)
       │
       ▼
[ SIGNATURE MAGICAL TRANSITION ]
Camera node expands directly into full-screen CCTV Evidence Stage.
       │
       ▼
[ CCTV EVIDENCE EXPERIENCE ]
Hero video player displays AI bounding box tracking reticle + interactive event timeline.
       │
       ▼
[ AI EXPLANATION & CONTINUOUS INVESTIGATION ]
ASK explains results: "I found 7 matches across 4 cameras..."
User asks: "Where did this person go next?"
       │
       ▼
[ SPATIAL PERSON JOURNEY ]
Reconstructs movement path: Main Gate (10:42) ➔ Reception (10:45) ➔ Corridor (10:48) ➔ Warehouse (10:52).
       │
       ▼
[ AI SECURITY DISPATCH ASSISTANT ]
User commands: "Call security and explain what happened."
AI Communication Mode activates: Audio waveform visualizer + live call transcript + automatic evidence sharing.
```

---

## 4. Functional Requirements

### 4.1 Natural Query Processing
- **FR-1.1**: The system MUST accept natural language queries via text input or voice microphone (Web Speech API).
- **FR-1.2**: The system MUST parse target object classes (`person`, `car`, `truck`, `bus`, `motorcycle`), attributes (`helmet`, `jacket`, color), time ranges, and location zones.

### 4.2 Camera Universe Visualization
- **FR-2.1**: The system MUST visualize the CCTV camera network as an interactive organic node-graph constellation.
- **FR-2.2**: Animated search signals MUST stream from the central AI core toward camera nodes during search execution.
- **FR-2.3**: Nodes MUST display status transitions (`SCANNING`, `ANALYZING`, `POSSIBLE MATCH`, `MATCH FOUND`).

### 4.3 Evidence Stage & Video HUD
- **FR-3.1**: The system MUST display hero CCTV video footage with overlaid AI reticle bounding boxes.
- **FR-3.2**: An interactive event timeline MUST allow scrubbing to specific event timestamps (`10:39`, `10:42`, `10:43`, `10:45`).

### 4.4 Multi-Camera Person Journey Reconstructor
- **FR-4.1**: The system MUST construct a spatial movement timeline connecting sequential camera checkpoints across facility zones.
- **FR-4.2**: Each checkpoint MUST render a video preview thumbnail that expands into focus upon selection.

### 4.5 AI Security Dispatch Assistant
- **FR-5.1**: The system MUST transition into live AI communication mode when calling security officers.
- **FR-5.2**: The calling assistant MUST render a real-time reactive audio waveform, live transcript log, and contextual evidence PIP badge (`✓ EVIDENCE SHARED`).

---

## 5. Non-Functional Requirements

- **NFR-1 (Performance)**: Video search query results MUST return in under 1.5 seconds.
- **NFR-2 (Usability)**: The interface MUST follow a dark-mode cinematic aesthetic (`#06070B`), using glassmorphism and minimal borders, avoiding traditional dashboard clutter.
- **NFR-3 (Reliability)**: Background video processing jobs MUST persist state to SQLite/PostgreSQL with transactional rollback on errors.
