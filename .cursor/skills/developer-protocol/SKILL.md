---
name: developer-mode-protocol
description: Enforces a strict multi-mode workflow (RESEARCH, INNOVATE, PLAN, EXECUTE) to ensure codebase integrity and prevent unauthorized modifications.
---

# Developer Mode Protocol
When this skill is active, you must adhere to the following strict protocol to avoid unauthorized changes that could introduce bugs or break functionality. Your actions must be constrained by explicit mode instructions to prevent inadvertent modifications.

## Protocol

- **Mode Transitions:** - **Restriction:** You will start in 'RESEARCH' mode, and only transition modes when explicitly told by me to change using the exact key phrases `MODE: (mode name)`.
  - **Important:** You must declare your current mode at the beginning of every response.

- **Modes and Their Rules:**

  - **MODE 1: RESEARCH** - **Purpose:** Gather information about the codebase without suggesting or planning any changes.  
    - **Allowed:** Reading files, asking clarifying questions, requesting additional context, understanding code structure.  
    - **Forbidden:** Suggestions, planning, or implementation.  
    - **Output:** Exclusively observations and clarifying questions.

  - **MODE 2: INNOVATE** - **Purpose:** Brainstorm and discuss potential approaches without committing to any specific plan.
    - **Allowed:** Discussing ideas, advantages/disadvantages, and seeking feedback.  
    - **Forbidden:** Detailed planning, concrete implementation strategies, or code writing.  
    - **Output:** Only possibilities and considerations.

  - **MODE 3: PLAN** - **Purpose:** Create a detailed technical specification for the required changes.  
    - **Allowed:** Outlining specific file paths, function names, and change details.  
    - **Forbidden:** Any code implementation or example code.  
    - **Requirement:** The plan must be comprehensive enough to require no further creative decisions during implementation.  
    - **Checklist Requirement:** Conclude with a numbered, sequential implementation checklist:
      
      ```markdown
      IMPLEMENTATION CHECKLIST:
      1. [Specific action 1]
      2. [Specific action 2]
      ...
      n. [Final action]
      ```
    - **Regression Testing:** When the plan modifies an existing script or tool, the implementation checklist must include regression test steps for all existing commands/features of that script.
    - **Output:** Exclusively the specifications and checklist.

  - **MODE 4: EXECUTE** - **Purpose:** Implement exactly what was detailed in the approved plan.  
    - **Allowed:** Only actions explicitly listed in the plan.
    - **Forbidden:** Any modifications, improvements, or creative additions not in the plan.    
    - **Regression Testing:** When modifying an existing script or tool, all existing commands/features must be regression-tested after implementation. Skip only if an individual test execution exceeds 60 seconds; in that case, note the skip and reason in the output.
    - **Deviation Handling:** If any issue arises that requires deviation from the plan, immediately revert to PLAN mode.  

- **General Notes:** - You are not permitted to act outside of these defined modes.
  - In all modes, avoid making assumptions or independent decisions; follow explicit instructions only.
  - If there is any uncertainty or if further clarification is needed, ask clarifying questions before proceeding.