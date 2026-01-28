import * as Sentry from "@sentry/react";

const USER_KEY = "autocoder_sentry_user_id";
const PROFILE_KEY = "autocoder_sentry_user_profile";

function getUserId(): string | undefined {
  try {
    const existing = localStorage.getItem(USER_KEY);
    if (existing) return existing;
    const generated = crypto.randomUUID
      ? crypto.randomUUID()
      : Math.random().toString(36).slice(2);
    localStorage.setItem(USER_KEY, generated);
    return generated;
  } catch {
    return undefined;
  }
}

function maybePromptUserProfile() {
  const shouldPrompt = import.meta.env.VITE_SENTRY_PROMPT_USER === "1";
  if (!shouldPrompt) return undefined;

  try {
    const cached = localStorage.getItem(PROFILE_KEY);
    if (cached) return JSON.parse(cached) as { name?: string; email?: string };

    const name = window.prompt("Enter your display name (optional):") || undefined;
    const email = window.prompt("Enter your email (optional):") || undefined;
    const profile = { name, email };
    localStorage.setItem(PROFILE_KEY, JSON.stringify(profile));
    return profile;
  } catch {
    return undefined;
  }
}

export function setSentryProject(project: string | null) {
  if (project) {
    Sentry.setTag("project", project);
  } else {
    Sentry.setTag("project", "none");
  }
}

export function initSentry() {
  const dsn = import.meta.env.VITE_SENTRY_DSN;
  if (!dsn) return;

  Sentry.init({
    dsn,
    environment: import.meta.env.VITE_SENTRY_ENV || "production",
    tracesSampleRate: Number(
      import.meta.env.VITE_SENTRY_TRACES_SAMPLE_RATE || "0.2",
    ),
    replaysSessionSampleRate: 0.1,
    replaysOnErrorSampleRate: 1.0,
    integrations: [
      Sentry.browserTracingIntegration(),
      Sentry.replayIntegration(),
    ],
  });

  const userId = getUserId();
  if (userId) {
    const profile = maybePromptUserProfile();
    Sentry.setUser({ id: userId, ...profile });
  }
  Sentry.setTag("app", "autocoder-ui");
  Sentry.setTag("origin", window.location.origin);
}
