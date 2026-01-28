/**
 * Hook for playing sounds when features move between columns
 * Uses Web Audio API to generate pleasant chime sounds
 */

import { useEffect, useRef } from "react";
import type { FeatureListResponse } from "../lib/types";

// Sound frequencies for different transitions (in Hz)
const SOUNDS = {
  // Feature started (pending -> in_progress): ascending tone
  started: [523.25, 659.25], // C5 -> E5
  // Feature completed (in_progress -> done): pleasant major chord arpeggio
  completed: [523.25, 659.25, 783.99], // C5 -> E5 -> G5
};

type SoundType = keyof typeof SOUNDS;

function playChime(type: SoundType): void {
  try {
    const audioContext = new (
      window.AudioContext ||
      (window as unknown as { webkitAudioContext: typeof AudioContext })
        .webkitAudioContext
    )();
    const frequencies = SOUNDS[type];
    const duration = type === "completed" ? 0.15 : 0.12;
    const totalDuration = frequencies.length * duration;

    frequencies.forEach((freq, index) => {
      const oscillator = audioContext.createOscillator();
      const gainNode = audioContext.createGain();

      oscillator.connect(gainNode);
      gainNode.connect(audioContext.destination);

      oscillator.type = "sine";
      oscillator.frequency.setValueAtTime(freq, audioContext.currentTime);

      // Envelope for smooth sound
      const startTime = audioContext.currentTime + index * duration;
      gainNode.gain.setValueAtTime(0, startTime);
      gainNode.gain.linearRampToValueAtTime(0.3, startTime + 0.02);
      gainNode.gain.exponentialRampToValueAtTime(0.01, startTime + duration);

      oscillator.start(startTime);
      oscillator.stop(startTime + duration);
    });

    // Clean up audio context after sounds finish
    setTimeout(
      () => {
        audioContext.close();
      },
      totalDuration * 1000 + 100,
    );
  } catch {
    // Audio not supported or blocked, fail silently
  }
}

interface FeatureState {
  pendingIds: Set<number>;
  inProgressIds: Set<number>;
  doneIds: Set<number>;
}

function getFeatureState(
  features: FeatureListResponse | undefined,
): FeatureState {
  return {
    pendingIds: new Set(features?.pending.map((f) => f.id) ?? []),
    inProgressIds: new Set(features?.in_progress.map((f) => f.id) ?? []),
    doneIds: new Set(features?.done.map((f) => f.id) ?? []),
  };
}

export function useFeatureSound(
  features: FeatureListResponse | undefined,
): void {
  const prevStateRef = useRef<FeatureState | null>(null);
  const isInitializedRef = useRef(false);

  useEffect(() => {
    if (!features) return;

    const currentState = getFeatureState(features);

    // Skip sound on initial load
    if (!isInitializedRef.current) {
      prevStateRef.current = currentState;
      isInitializedRef.current = true;
      return;
    }

    const prevState = prevStateRef.current;
    if (!prevState) {
      prevStateRef.current = currentState;
      return;
    }

    // Check for features that moved to in_progress (started)
    for (const id of currentState.inProgressIds) {
      if (prevState.pendingIds.has(id) && !prevState.inProgressIds.has(id)) {
        playChime("started");
        break; // Only play once even if multiple features moved
      }
    }

    // Check for features that moved to done (completed)
    for (const id of currentState.doneIds) {
      if (
        !prevState.doneIds.has(id) &&
        (prevState.inProgressIds.has(id) || prevState.pendingIds.has(id))
      ) {
        playChime("completed");
        break; // Only play once even if multiple features moved
      }
    }

    prevStateRef.current = currentState;
  }, [features]);
}
