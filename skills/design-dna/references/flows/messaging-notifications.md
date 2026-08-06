# Messaging and notifications

Use this for inboxes, chat, comments, announcements, notification centers,
delivery status, and preference controls. Distinguish human messages, system
events, marketing, and automated or generated content.

## Model the communication

Record:

- sender and recipient roles;
- channel, subject or thread, and audience scope;
- draft, queued, sending, sent, delivered, read, failed, edited, deleted, or
  moderated states the system actually knows;
- ordering, pagination, history, retention, and search;
- urgency, notification policy, and escalation;
- privacy, consent, abuse, and legal constraints.

Do not imply presence, typing, read status, delivery, encryption, moderation,
or a human response when the system cannot prove it.

## Design the inbox and thread

- Preserve sender, timestamp, sequence, grouping, unread boundary, and reply context.
- Keep selection and scroll position stable through updates.
- Provide useful empty, loading, offline, stale, removed, blocked, and failed states.
- Distinguish a new message from an edit, deletion, reaction, system event, or
  automated action.
- Expose attachment name, type, size, progress, failure, and safe removal.
- Make quoting, reply-to, mention, and thread scope clear before sending.
- Choose message grouping and container treatment from the communication
  model. Bubbles, a log, a comment thread, a structured event view, or another
  form can each be correct; revise repetition only when it obscures chronology,
  authorship, status, density, or the actual task.

## Compose and send safely

Preserve drafts through recoverable failure. Expose pending state and prevent
accidental duplicates. Provide retry, cancel, edit, delete, or undo only when
the backend contract supports it. Confirm audience and channel before a broad,
external, or irreversible send. Keep destructive moderation and bulk actions
distinct from ordinary reply.

For generated or suggested content, show the editable draft, source and
audience context, approval boundary, and actual sender. Never auto-send unless
explicitly authorized and operationally safeguarded.

## Notification preferences

Group preferences by purpose and consequence, not merely delivery technology.
Clarify:

- required service, security, transactional, digest, social, and marketing categories;
- email, SMS, push, in-product, webhook, or other channel availability;
- per-event, per-project, per-workspace, or global scope;
- frequency, quiet hours, timezone, batching, and urgent exceptions;
- save behavior, verification, unsubscribe, and propagation delay.

Do not represent legally or operationally required notices as optional. Do not
hide marketing consent inside service preferences.

## Presence, live regions, and motion

Announce incoming or send-status changes without repeatedly interrupting the
screen reader or moving focus. Let users pause or reduce rapid updates. Avoid
auto-scrolling when the user is reading history; provide a clear new-message
control. Preserve meaning without animation, sound, color, or haptics alone.

## Safety and moderation

When user-generated communication exists, design the real report, block, mute,
appeal, evidence, and emergency boundaries. Protect reporter privacy and
explain scope and consequences. Do not promise response times, monitoring, or
safety intervention without approved operations.

## Verify and escalate

Test long threads, no messages, unread state, concurrent replies, offline
draft, retry, duplicate prevention, delayed delivery, edits, deletion,
attachments, blocked users, missing permission, preference propagation,
timezone boundaries, screen-reader announcements, keyboard, touch, zoom, and
reduced motion.

Require security, privacy, legal, trust-and-safety, deliverability, and
operations specialists for encryption claims, retention, abuse handling,
regulated communication, production sending, or emergency response.
