# Shipped-Artifact Evidence with REA

REA (`rea-agents`) inspects shipped artifacts and records each result as Evidence with an Evidence ID, observations, inferences, unknowns, and limitations. In this skill, REA only establishes facts about artifacts. It never decides a verdict on its own.

## When to use REA

Use REA when a candidate's decisive fact lives in a shipped artifact whose source is not in the target: a native binary, package, APK, .NET assembly, Electron or JavaScript application bundle, firmware image, or a recorded HAR or packet capture. Typical hand-offs come from [memory-safety-and-binary.md](memory-safety-and-binary.md), [supply-chain-and-release.md](supply-chain-and-release.md), [desktop-mobile-and-local-ipc.md](desktop-mobile-and-local-ipc.md), and [client-side.md](client-side.md).

Do not use REA for ordinary source-repository analysis.

## Availability

- REA is available when the dynamic tool catalog has an REA namespace, or when `rea` is on `PATH`.
- If REA is unavailable, the lead stays `needs_validation` with the blocker `REA unavailable: <decisive fact>`.
- Never install REA, run `npx rea-agents`, or change any client configuration. Native analysis also needs Ghidra, Hopper, or IDA; if the provider is missing, record that as the blocker.

## Allowed: static analysis

Static tools read an artifact or a recorded capture without executing it. Examples:

- `inspect_artifact`, `inspect_binary_layout`, `open_binary`, `binary_overview`, `analyze_function`, `close_binary`, `inspect_analysis_view`
- `analyze_javascript_application`, `inspect_web_network_capture`, `inspect_packet_capture`
- `inspect_macho`, `inspect_elf_notes`, `inspect_pe_resources`, `inspect_pe_certificates`, `inspect_native_exports`, `inspect_go_binary`, `inspect_rust_binary`
- `inspect_android_package`, `inspect_apk_signature`, `inspect_managed_artifact`, `inspect_wasm_artifact`, `inspect_python_pyc`, `inspect_plist`, `inspect_sqlite_database`
- `compare_artifacts`, `compare_functions`, `compare_bundles`, `find_changed_behavior`, `build_call_path`, `correlate_static_and_runtime`
- `record_unknown` and `update_unknown`

`extract_artifact` and `export_evidence_bundle` may write only under the run's `<output-dir>/agents/<agent-id>/scratch/`.

## Allowed: passive runtime observation

Only on a browser or Electron instance that the user already opened, through a loopback CDP endpoint that the user supplies, with the user performing every action:

- `list_browser_targets`, `inspect_web_page`, `observe_web_session`
- `list_electron_targets`, `inspect_electron_fuses`
- `inspect_web_event_listeners`, `compare_web_captures`, `capture_web_screenshot`
- `discover_webmcp_tools`, for inventory only; never invoke a discovered tool

## Forbidden

- `capture_browser_scenario`, because REA navigates and acts on the target.
- `observe_web_execution`, because it resets counters and changes optimization state.
- Process captures, Frida, debuggers, and any tool that launches, attaches to, or injects into the target.
- `rea environment-serve`, traffic replay, and invoking page-declared tools.

## Recording

- The parent saves each returned Evidence record to `<output-dir>/rea/<evidence_id>.json`.
- A finding cites REA Evidence in `evidence[].description` as `REA <evidence_id>: <observation>`. Its `file` and `line` point to the source location that consumes the artifact fact.
- An unresolved artifact fact goes into `blockers`, naming the Evidence ID and the remaining unknown.
- REA Evidence resolves artifact facts only. A `confirmed` record still meets the full evidence bar in [validation-and-reporting.md](validation-and-reporting.md). Passive observation counts as an owner-observed result only when the user performed the action.
- `report-schema.json` is unchanged; REA adds no fields.
