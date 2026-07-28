# Motion and interaction

Use this when defining transitions, feedback, scrolling, direct manipulation, or animated media.

## Give motion a purpose

Use motion to:

- confirm an action;
- connect cause and effect;
- preserve spatial continuity;
- explain state or hierarchy;
- direct attention to a meaningful change;
- support a deliberate narrative sequence.

Do not animate every section or card to make the page feel active. Repeated fade-up, hover-lift, glow, typewriter, counter, marquee, and pulse treatments are candidate risks when they carry no meaning.

## Define an interaction system

Specify:

- trigger and user intent;
- start, intermediate, completion, interruption, and error states;
- duration, easing, distance, and choreography tokens;
- focus and keyboard behavior;
- touch and no-hover alternative;
- reduced-motion result;
- loading and low-performance behavior.

Keep feedback near the action that caused it. Do not delay essential state changes for animation.

## Protect control

- Avoid scroll hijacking and unexpected navigation.
- Make auto-moving content pausable when required.
- Stop background work and animation when no longer visible or relevant.
- Provide an alternative to dragging and precise gestures.
- Do not make hover reveal information required to act.
- Preserve focus through route, dialog, menu, and validation transitions.
- Make destructive and irreversible actions explicit and recoverable where possible.

## Implement efficiently

- Prefer transform and opacity for frequent animation.
- Avoid layout-thrashing listeners and unbounded scroll work.
- Use progressive enhancement for nonessential behavior.
- Treat view transitions and scroll-driven animation as progressive
  enhancements: preserve navigation, history, reading order, deep links, and a
  complete no-effect path when the API is absent or the animation is cancelled.
- Respect `prefers-reduced-motion`; reduce the cognitive movement, not merely the duration.
- Test interruption, rapid repeat input, slow devices, and background-tab return.

## Review

Check whether the experience remains complete with animation disabled. Verify keyboard, touch, mouse, coarse pointer, reduced motion, zoom, screen-reader announcements, performance, and recovery after cancellation or failure.
