# Team Lifecycle and Role Session Health

Runtime rules for auditing, reusing, closing, and replacing role sessions in PL-led feature work. Read this at the start of every `/pl` request before spawning anyone, when a role session goes idle without a delivered result or misbehaves, and at completion or cancellation. Spawn policy (roles, models, timing, batching) lives in `roles.md`; the discussion loop lives in `debate-protocol.md`. Host-specific recovery steps (transcript lookup, session restore) live in SKILL.md Platform Behavior.

## Team Lifecycle

At the start of every `/pl` request:

1. Inspect active role sessions and the task ledger before spawning anyone.
2. Reuse a healthy role session only for a continuation of the same feature when its role and context still match.
3. For a new feature, settle the previous tasks, ask every old role session to close, and confirm graceful or forced close before spawning fresh role sessions. Verify genuinely completed tasks; delete obsolete pending tasks with task controls and record the abandonment in the old feature note. Never mark abandoned work completed. If an old close cannot be confirmed, do not spawn a replacement in the same session: use a new host session for hard isolation or continue lead-only with the overlap risk recorded. Do not carry stale conclusions across feature boundaries.
4. Prefix every ledger entry subject with `[<feature-slug>]`. Ledger entries can outlive role sessions, so the prefix keeps sequential feature ledgers distinguishable.
5. Do not reuse a runtime name that already appeared in the current session. Use the next suffix such as `pl-architect-r2` for both replacements and later features.
6. After a session restore, reconcile the persisted ledger but assume earlier role sessions are gone until the host proves otherwise; spawn replacements instead of messaging missing sessions.
7. Never edit the host's session or ledger state files by hand. Use the host's session and ledger controls; the host owns runtime config and retention.

During work:

1. Wait for prerequisite analysis or implementation tasks before starting dependent work.
2. Monitor stuck or stale task states; verify the output, then correct task status or replace the role session when necessary.
3. Require plan approval before a role session edits for complex or risky implementation work.
4. Keep the task ledger authoritative. Do not let a role session start role work without an owned ledger entry; reconstruct missing entries before continuing.
5. After a role session's final deliverable is accepted, close it when no dependency, revision, or re-review remains. Keep an idle role session only for a named follow-up within the same feature.
6. A role session the host hides after an idle timeout may still be running and addressable. Do not treat a hidden session as closed; confirm through the ledger state or a named message.

At completion or cancellation:

1. Confirm no required task remains pending or in progress.
2. For every name recorded under Spawned, confirm you can quote that session's delivered text; a name you cannot quote was never a session and must be rewritten as `not spawned` with the reason.
3. Collect concise outputs and update the feature note.
4. Ask every remaining role session to close by runtime name. If a role session rejects because work is active, resolve the task or delete it as obsolete and record the abandonment, then retry.
5. Wait a bounded time for close acknowledgement. If the ledger entry is settled and no required operation is still running, force-close the session through the host's close-session mechanism and confirm it stopped. Record graceful closes, force-closes, and any unconfirmed timeout separately.
6. Do not hand-clean session state; the host owns cleanup and retention.
7. Leave no idle role sessions or unsettled ledger entries after the feature is closed. An unconfirmed stop prevents `done` and must be reported as `done-with-risks` when the implementation is otherwise complete.

## Role Session Health and Restart

Treat role sessions as replaceable.

This state exists only on hosts whose role sessions can go idle without returning; on hosts where a session always returns or fails there is nothing to triage (see SKILL.md Platform Behavior).

If a role session goes idle without a delivered result, triage before any correction or replacement:

1. Check its ledger entry. An untouched entry usually means the memo was never delivered through the named channel, not that the role work failed.
2. Recover undelivered work through the host's transcript or session inspection (SKILL.md Platform Behavior names the steps per host). Treat a recovered memo as the deliverable.
3. Send one message through the delivery channel telling the role session to deliver the memo through the named channel and settle its owned ledger entry before going idle.
4. Escalate below only when the transcript shows no usable work or the role session stays unresponsive after that nudge. Do not conclude role sessions cannot reply or fall back to lead-only passes without completing this triage.

If a role session is stale, confused, in the wrong role, using the wrong model, ignoring constraints, looping, or producing low-quality output:

1. Try at most one concise correction if the issue is minor.
2. For material issues, ask the role session to close by name. If it does not stop after a bounded wait and no required operation should continue, force-close it through the host's close-session mechanism and confirm.
3. Spawn a replacement only after the old session is confirmed stopped, using the same named `team-pl-*` agent type and a runtime suffix such as `-r2`, not a generic role session. If stop cannot be confirmed, do not spawn a replacement in the same session; use a new host session or continue lead-only and record the overlap risk.
4. Give the replacement a clean restart brief:
   - Current feature request
   - Relevant repo and memory facts
   - Accepted PL decisions so far
   - The exact role question
   - What to ignore from the stale role session output
5. Record the restart in the feature note under Discussion Summary or Open Questions.

Do not rely on later prompts to repair a wrong-model role session. Check for an invocation model override, a host-level subagent model setting, and a higher-priority same-name definition. Remove the override when possible; replace the role session only after the cause is resolved. Otherwise use the recorded lead-pass fallback rather than looping.
