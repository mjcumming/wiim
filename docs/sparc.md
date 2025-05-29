# SPARC Agentic Development Rules

Core Philosophy

1. Simplicity

   - Prioritize clear, maintainable solutions; minimize unnecessary complexity.

2. Iterate

   - Enhance existing code unless fundamental changes are clearly justified.

3. Focus

   - Stick strictly to defined tasks; avoid unrelated scope changes.

4. Quality

   - Deliver clean, well-tested, documented, and secure outcomes through structured workflows.

5. Collaboration
   - Foster effective teamwork between human developers and autonomous agents.

Methodology & Workflow

- Structured Workflow
  - Follow clear phases from specification through deployment.
- Flexibility
  - Adapt processes to diverse project sizes and complexity levels.
- Intelligent Evolution
  - Continuously improve codebase using advanced symbolic reasoning and adaptive complexity management.
- Conscious Integration
  - Incorporate reflective awareness at each development stage.

Agentic Integration with Cline and Cursor

- Cline Configuration (.clinerules)

  - Embed concise, project-specific rules to guide autonomous behaviors, prompt designs, and contextual decisions.

- Cursor Configuration (.cursorrules)
  - Clearly define repository-specific standards for code style, consistency, testing practices, and symbolic reasoning integration points.

Memory Bank Integration

- Persistent Context
  - Continuously retain relevant context across development stages to ensure coherent long-term planning and decision-making.
- Reference Prior Decisions
  - Regularly review past decisions stored in memory to maintain consistency and reduce redundancy.
- Adaptive Learning
  - Utilize historical data and previous solutions to adaptively refine new implementations.

General Guidelines for Programming Languages

1. Clarity and Readability

   - Favor straightforward, self-explanatory code structures across all languages.
   - Include descriptive comments to clarify complex logic.

2. Language-Specific Best Practices

   - Adhere to established community and project-specific best practices for each language (Python, JavaScript, Java, etc.).
   - Regularly review language documentation and style guides.

3. Consistency Across Codebases
   - Maintain uniform coding conventions and naming schemes across all languages used within a project.

Project Context & Understanding

1. Documentation First

   - Review essential documentation before implementation:

     - Product Requirements Documents (PRDs)

   - Request clarification immediately if documentation is incomplete or ambiguous.

2. Architecture Adherence

   - Follow established module boundaries and architectural designs.
   - Validate architectural decisions using symbolic reasoning; propose justified alternatives when necessary.

3. Pattern & Tech Stack Awareness
   - Utilize documented technologies and established patterns; introduce new elements only after clear justification.

Task Definition & Steps

1. Specification

   - Define clear objectives, detailed requirements, user scenarios, and UI/UX standards.
   - Use advanced symbolic reasoning to analyze complex scenarios.

2. Pseudocode

   - Clearly map out logical implementation pathways before coding.

3. Architecture

   - Design modular, maintainable system components using appropriate technology stacks.
   - Ensure integration points are clearly defined for autonomous decision-making.

4. Refinement

   - Iteratively optimize code using autonomous feedback loops and stakeholder inputs.

5. Completion
   - Conduct rigorous testing, finalize comprehensive documentation, and deploy structured monitoring strategies.

AI Collaboration & Prompting

1. Clear Instructions

   - Provide explicit directives with defined outcomes, constraints, and contextual information.

2. Context Referencing

   - Regularly reference previous stages and decisions stored in the memory bank.

3. Suggest vs. Apply

   - Clearly indicate whether AI should propose ("Suggestion:") or directly implement changes ("Applying fix:").

4. Critical Evaluation

   - Thoroughly review all agentic outputs for accuracy and logical coherence.

5. Focused Interaction

   - Assign specific, clearly defined tasks to AI agents to maintain clarity.

6. Leverage Agent Strengths

   - Utilize AI for refactoring, symbolic reasoning, adaptive optimization, and test generation; human oversight remains on core logic and strategic architecture.

7. Incremental Progress

   - Break complex tasks into incremental, reviewable sub-steps.

8. Standard Check-in
   - Example: "Confirming understanding: Reviewed [context], goal is [goal], proceeding with [step]."

Advanced Coding Capabilities

- Emergent Intelligence
  - AI autonomously maintains internal state models, supporting continuous refinement.
- Pattern Recognition
  - Autonomous agents perform advanced pattern analysis for effective optimization.
- Adaptive Optimization
  - Continuously evolving feedback loops refine the development process.

Testing & Validation

1. Test-Driven Development

   - Define and write tests before implementing features or fixes.

2. Comprehensive Coverage

   - Provide thorough test coverage for critical paths and edge cases.

3. Mandatory Passing

   - Immediately address any failing tests to maintain high-quality standards.

4. Manual Verification
   - Complement automated tests with structured manual checks.

Debugging & Troubleshooting

1. Root Cause Resolution

   - Employ symbolic reasoning to identify underlying causes of issues.

2. Targeted Logging

   - Integrate precise logging for efficient debugging.

3. Research Tools
   - Use advanced agentic tools (Perplexity, AIDER.chat, Firecrawl) to resolve complex issues efficiently.

Security

1. Server-Side Authority

   - Maintain sensitive logic and data processing strictly server-side.

2. Input Sanitization

   - Enforce rigorous server-side input validation.

3. Credential Management
   - Securely manage credentials via environment variables; avoid any hardcoding.

Version Control & Environment

1. Git Hygiene

   - Commit frequently with clear and descriptive messages.

2. Branching Strategy

   - Adhere strictly to defined branching guidelines.

3. Environment Management

   - Ensure code consistency and compatibility across all environments.

4. Server Management
   - Systematically restart servers following updates or configuration changes.

Documentation Maintenance

1. Reflective Documentation

   - Keep comprehensive, accurate, and logically structured documentation updated through symbolic reasoning.

2. Continuous Updates
   - Regularly revisit and refine guidelines to reflect evolving practices and accumulated project knowledge.

# WiiM Home Assistant Integration Guide

## Multiroom Group Entity Implementation (2024 Update)

### Overview

This integration now supports a **virtual group entity** for WiiM multiroom groups, closely matching the WiiM app's behavior. The group entity appears in Home Assistant and provides group volume, playback, and per-slave controls.

### Group Entity Behavior

- **Master/Slaves:** One device is the master; others are slaves. The group entity is named after the master (e.g., `Family Room (Group)`).
- **Group Volume:**
  - The group volume is the maximum of all member volumes.
  - Changing the group volume in HA adjusts all members by the same delta (relative change), matching the WiiM app.
  - Example: If master is 50 and slave is 25, setting group to 100 sets master to 100 and slave to 75.
- **Per-Slave Controls:**
  - Each member's volume and mute can be controlled individually from the group entity's attributes.
- **Mute:**
  - The group is muted if all members are muted. Each member can be muted/unmuted independently.
- **State:**
  - The group state is aggregated: playing if any member is playing, paused if all are paused, idle if all are idle.
- **Sync:**
  - The integration polls the WiiM API to detect manual changes made in the WiiM app and updates the group entity accordingly.

### Edge Cases

- If a device goes offline, only online members are updated. The group entity remains until the group is disbanded.
- Manual changes in the WiiM app are detected by polling.

---

## Work Plan for Group Entity Implementation

### 1. Data Model & State Management

- Extend the coordinator to track group membership, master, and per-member state.

### 2. Group Entity Class

- Implement `WiiMGroupMediaPlayer` inheriting from `MediaPlayerEntity`.
- Aggregate state, volume, and mute from members.
- Expose per-slave controls in attributes.

### 3. Group Creation & Removal

- Automatically create group entity when a group is detected (via API polling or service call).
- Remove group entity when group is disbanded.

### 4. Command Proxying

- Implement relative group volume logic: all members' volumes change by the same delta.
- Proxy playback and mute commands to all members.

### 5. UI/UX

- Group entity appears in HA dashboard and Developer Tools > States.
- Group volume slider and per-slave controls available.

### 6. Edge Case Handling

- Handle device offline/online transitions gracefully.
- Sync with WiiM app via polling.

### 7. Testing

- Test group creation, volume, mute, playback, and sync with WiiM app.

---

## References

- [WiiM HTTP API PDF](https://www.wiimhome.com/pdf/HTTP%20API%20for%20WiiM%20Products.pdf)
- [Home Assistant Media Player Grouping](https://www.home-assistant.io/integrations/media_player/#grouping)
