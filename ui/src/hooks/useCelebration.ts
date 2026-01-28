/**
 * Hook for triggering celebration effects when all features are complete
 * Plays confetti cannons from both sides and a triumphant fanfare
 */

import { useEffect, useRef } from "react";
import confetti from "canvas-confetti";
import type { FeatureListResponse } from "../lib/types";

/**
 * Play a triumphant fanfare using Web Audio API
 * Rising major chord progression: C5 -> E5 -> G5 -> C6
 */
function playFanfare(): void {
  try {
    const audioContext = new (
      window.AudioContext ||
      (window as unknown as { webkitAudioContext: typeof AudioContext })
        .webkitAudioContext
    )();

    // Frequencies for triumphant fanfare (C major arpeggio going up)
    const notes = [
      { freq: 523.25, start: 0 }, // C5
      { freq: 659.25, start: 0.15 }, // E5
      { freq: 783.99, start: 0.3 }, // G5
      { freq: 1046.5, start: 0.45 }, // C6 (octave higher)
    ];

    const noteDuration = 0.25;

    notes.forEach(({ freq, start }) => {
      const oscillator = audioContext.createOscillator();
      const gainNode = audioContext.createGain();

      oscillator.connect(gainNode);
      gainNode.connect(audioContext.destination);

      oscillator.type = "sine";
      oscillator.frequency.setValueAtTime(
        freq,
        audioContext.currentTime + start,
      );

      // Envelope for smooth, triumphant sound
      const startTime = audioContext.currentTime + start;
      gainNode.gain.setValueAtTime(0, startTime);
      gainNode.gain.linearRampToValueAtTime(0.4, startTime + 0.03);
      gainNode.gain.setValueAtTime(0.4, startTime + noteDuration * 0.6);
      gainNode.gain.exponentialRampToValueAtTime(
        0.01,
        startTime + noteDuration,
      );

      oscillator.start(startTime);
      oscillator.stop(startTime + noteDuration);
    });

    // Add a final sustained chord for extra triumph
    const chordFreqs = [523.25, 659.25, 783.99, 1046.5]; // C major chord
    const chordStart = 0.65;
    const chordDuration = 0.5;

    chordFreqs.forEach((freq) => {
      const oscillator = audioContext.createOscillator();
      const gainNode = audioContext.createGain();

      oscillator.connect(gainNode);
      gainNode.connect(audioContext.destination);

      oscillator.type = "sine";
      oscillator.frequency.setValueAtTime(
        freq,
        audioContext.currentTime + chordStart,
      );

      const startTime = audioContext.currentTime + chordStart;
      gainNode.gain.setValueAtTime(0, startTime);
      gainNode.gain.linearRampToValueAtTime(0.2, startTime + 0.05);
      gainNode.gain.setValueAtTime(0.2, startTime + chordDuration * 0.5);
      gainNode.gain.exponentialRampToValueAtTime(
        0.01,
        startTime + chordDuration,
      );

      oscillator.start(startTime);
      oscillator.stop(startTime + chordDuration);
    });

    // Clean up audio context after sounds finish
    setTimeout(() => {
      audioContext.close();
    }, 1500);
  } catch {
    // Audio not supported or blocked, fail silently
  }
}

/**
 * Fire confetti cannons from both sides of the screen
 */
function fireConfetti(): void {
  const duration = 2000;
  const end = Date.now() + duration;

  // Initial burst from both sides
  confetti({
    particleCount: 100,
    spread: 70,
    origin: { x: 0, y: 0.6 },
    angle: 60,
    colors: ["#ff6b6b", "#4ecdc4", "#45b7d1", "#96ceb4", "#ffeaa7", "#dfe6e9"],
  });

  confetti({
    particleCount: 100,
    spread: 70,
    origin: { x: 1, y: 0.6 },
    angle: 120,
    colors: ["#ff6b6b", "#4ecdc4", "#45b7d1", "#96ceb4", "#ffeaa7", "#dfe6e9"],
  });

  // Continue firing for a bit
  const interval = setInterval(() => {
    if (Date.now() > end) {
      clearInterval(interval);
      return;
    }

    confetti({
      particleCount: 30,
      spread: 60,
      origin: { x: 0, y: 0.6 },
      angle: 60,
      colors: [
        "#ff6b6b",
        "#4ecdc4",
        "#45b7d1",
        "#96ceb4",
        "#ffeaa7",
        "#dfe6e9",
      ],
    });

    confetti({
      particleCount: 30,
      spread: 60,
      origin: { x: 1, y: 0.6 },
      angle: 120,
      colors: [
        "#ff6b6b",
        "#4ecdc4",
        "#45b7d1",
        "#96ceb4",
        "#ffeaa7",
        "#dfe6e9",
      ],
    });
  }, 250);
}

/**
 * Check if all features are complete (none pending or in progress, at least one done)
 */
function isAllComplete(features: FeatureListResponse | undefined): boolean {
  if (!features) return false;
  return (
    features.pending.length === 0 &&
    features.in_progress.length === 0 &&
    features.done.length > 0
  );
}

/**
 * Hook that triggers celebration when all features are complete
 * Tracks per-project to allow re-celebration when switching between completed projects
 */
export function useCelebration(
  features: FeatureListResponse | undefined,
  projectName: string | null,
): void {
  // Track which projects have celebrated in this session
  const celebratedProjectsRef = useRef<Set<string>>(new Set());
  // Track if we've initialized for the current project (to avoid celebrating on initial load)
  const initializedForProjectRef = useRef<string | null>(null);

  useEffect(() => {
    if (!features || !projectName) return;

    const isComplete = isAllComplete(features);

    // If this is a new project, mark as initialized but don't celebrate yet
    // This prevents celebrating when first loading an already-complete project
    if (initializedForProjectRef.current !== projectName) {
      initializedForProjectRef.current = projectName;
      // If project is already complete on first load, mark it as celebrated
      // so we don't trigger when data refreshes
      if (isComplete) {
        celebratedProjectsRef.current.add(projectName);
      }
      return;
    }

    // Check if we should celebrate
    if (isComplete && !celebratedProjectsRef.current.has(projectName)) {
      // Mark as celebrated before firing to prevent double-triggers
      celebratedProjectsRef.current.add(projectName);

      // Fire the celebration!
      fireConfetti();
      playFanfare();
    }
  }, [features, projectName]);
}
