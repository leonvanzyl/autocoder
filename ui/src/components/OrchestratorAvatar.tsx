import type { OrchestratorState } from "../lib/types";

interface OrchestratorAvatarProps {
  state: OrchestratorState;
  size?: "sm" | "md" | "lg";
}

const SIZES = {
  sm: { svg: 32, font: "text-xs" },
  md: { svg: 48, font: "text-sm" },
  lg: { svg: 64, font: "text-base" },
};

// Maestro color scheme - Deep violet
const MAESTRO_COLORS = {
  primary: "#7C3AED", // Violet-600
  secondary: "#A78BFA", // Violet-400
  accent: "#EDE9FE", // Violet-100
  baton: "#FBBF24", // Amber-400 for the baton
  gold: "#F59E0B", // Amber-500 for accents
};

// Maestro SVG - Robot conductor with baton
function MaestroSVG({
  size,
  state,
}: {
  size: number;
  state: OrchestratorState;
}) {
  // Animation transform based on state
  const batonAnimation =
    state === "spawning"
      ? "animate-conducting"
      : state === "scheduling"
        ? "animate-baton-tap"
        : "";

  return (
    <svg width={size} height={size} viewBox="0 0 64 64" fill="none">
      {/* Conductor's podium hint */}
      <rect
        x="22"
        y="54"
        width="20"
        height="6"
        rx="2"
        fill={MAESTRO_COLORS.primary}
        opacity="0.3"
      />

      {/* Robot body - formal conductor style */}
      <rect
        x="18"
        y="28"
        width="28"
        height="26"
        rx="4"
        fill={MAESTRO_COLORS.primary}
      />

      {/* Tuxedo front / formal vest */}
      <rect x="26" y="32" width="12" height="18" fill={MAESTRO_COLORS.accent} />
      <rect
        x="30"
        y="32"
        width="4"
        height="18"
        fill={MAESTRO_COLORS.secondary}
      />

      {/* Bow tie */}
      <path d="M27,30 L32,33 L37,30 L32,32 Z" fill={MAESTRO_COLORS.gold} />

      {/* Robot head */}
      <rect
        x="16"
        y="6"
        width="32"
        height="24"
        rx="4"
        fill={MAESTRO_COLORS.secondary}
      />

      {/* Conductor's cap */}
      <rect
        x="14"
        y="2"
        width="36"
        height="8"
        rx="2"
        fill={MAESTRO_COLORS.primary}
      />
      <rect
        x="20"
        y="0"
        width="24"
        height="4"
        rx="2"
        fill={MAESTRO_COLORS.primary}
      />
      <circle cx="32" cy="2" r="3" fill={MAESTRO_COLORS.gold} />

      {/* Eyes */}
      <circle cx="24" cy="16" r="4" fill="white" />
      <circle cx="40" cy="16" r="4" fill="white" />
      <circle cx="25" cy="16" r="2" fill={MAESTRO_COLORS.primary} />
      <circle cx="41" cy="16" r="2" fill={MAESTRO_COLORS.primary} />

      {/* Smile */}
      <path
        d="M26,24 Q32,28 38,24"
        stroke="white"
        strokeWidth="2"
        fill="none"
        strokeLinecap="round"
      />

      {/* Arms */}
      <rect
        x="8"
        y="32"
        width="10"
        height="4"
        rx="2"
        fill={MAESTRO_COLORS.primary}
      />
      <rect
        x="46"
        y="28"
        width="10"
        height="4"
        rx="2"
        fill={MAESTRO_COLORS.primary}
        className={batonAnimation}
        style={{ transformOrigin: "46px 30px" }}
      />

      {/* Hand holding baton */}
      <circle
        cx="56"
        cy="30"
        r="4"
        fill={MAESTRO_COLORS.secondary}
        className={batonAnimation}
        style={{ transformOrigin: "46px 30px" }}
      />

      {/* Baton */}
      <g className={batonAnimation} style={{ transformOrigin: "56px 30px" }}>
        <line
          x1="56"
          y1="26"
          x2="62"
          y2="10"
          stroke={MAESTRO_COLORS.baton}
          strokeWidth="2"
          strokeLinecap="round"
        />
        <circle cx="62" cy="10" r="2" fill={MAESTRO_COLORS.gold} />
      </g>

      {/* Subtle music notes when active */}
      {(state === "spawning" || state === "monitoring") && (
        <>
          <text
            x="4"
            y="20"
            fontSize="8"
            fill={MAESTRO_COLORS.secondary}
            className="animate-pulse"
          >
            &#9834;
          </text>
          <text
            x="58"
            y="48"
            fontSize="8"
            fill={MAESTRO_COLORS.secondary}
            className="animate-pulse"
            style={{ animationDelay: "0.3s" }}
          >
            &#9835;
          </text>
        </>
      )}
    </svg>
  );
}

// Animation classes based on orchestrator state
function getStateAnimation(state: OrchestratorState): string {
  switch (state) {
    case "idle":
      return "animate-bounce-gentle";
    case "initializing":
      return "animate-thinking";
    case "scheduling":
      return "animate-thinking";
    case "spawning":
      return "animate-working";
    case "monitoring":
      return "animate-bounce-gentle";
    case "complete":
      return "animate-celebrate";
    default:
      return "";
  }
}

// Glow effect based on state
function getStateGlow(state: OrchestratorState): string {
  switch (state) {
    case "initializing":
      return "shadow-[0_0_12px_rgba(124,58,237,0.4)]";
    case "scheduling":
      return "shadow-[0_0_10px_rgba(167,139,250,0.5)]";
    case "spawning":
      return "shadow-[0_0_16px_rgba(124,58,237,0.6)]";
    case "monitoring":
      return "shadow-[0_0_8px_rgba(167,139,250,0.4)]";
    case "complete":
      return "shadow-[0_0_20px_rgba(112,224,0,0.6)]";
    default:
      return "";
  }
}

// Get human-readable state description for accessibility
function getStateDescription(state: OrchestratorState): string {
  switch (state) {
    case "idle":
      return "waiting";
    case "initializing":
      return "initializing features";
    case "scheduling":
      return "selecting next features";
    case "spawning":
      return "spawning agents";
    case "monitoring":
      return "monitoring progress";
    case "complete":
      return "all features complete";
    default:
      return state;
  }
}

export function OrchestratorAvatar({
  state,
  size = "md",
}: OrchestratorAvatarProps) {
  const { svg: svgSize } = SIZES[size];
  const stateDesc = getStateDescription(state);
  const ariaLabel = `Orchestrator Maestro is ${stateDesc}`;

  return (
    <div
      className="flex flex-col items-center gap-1"
      role="status"
      aria-label={ariaLabel}
      aria-live="polite"
    >
      <div
        className={`
          rounded-full p-1 transition-all duration-300
          ${getStateAnimation(state)}
          ${getStateGlow(state)}
        `}
        style={{ backgroundColor: MAESTRO_COLORS.accent }}
        title={ariaLabel}
        role="img"
        aria-hidden="true"
      >
        <MaestroSVG size={svgSize} state={state} />
      </div>
    </div>
  );
}
