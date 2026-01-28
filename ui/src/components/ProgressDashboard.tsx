import { Wifi, WifiOff } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

interface ProgressDashboardProps {
  passing: number;
  total: number;
  percentage: number;
  isConnected: boolean;
}

export function ProgressDashboard({
  passing,
  total,
  percentage,
  isConnected,
}: ProgressDashboardProps) {
  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0 pb-4">
        <CardTitle className="text-xl uppercase tracking-wide">
          Progress
        </CardTitle>
        <Badge
          variant={isConnected ? "default" : "destructive"}
          className="gap-1"
        >
          {isConnected ? (
            <>
              <Wifi size={14} />
              Live
            </>
          ) : (
            <>
              <WifiOff size={14} />
              Offline
            </>
          )}
        </Badge>
      </CardHeader>

      <CardContent>
        {/* Large Percentage */}
        <div className="text-center mb-6">
          <span className="inline-flex items-baseline">
            <span className="text-6xl font-bold tabular-nums">
              {percentage.toFixed(1)}
            </span>
            <span className="text-3xl font-semibold text-muted-foreground">
              %
            </span>
          </span>
        </div>

        {/* Progress Bar */}
        <div className="h-3 bg-muted rounded-full overflow-hidden mb-6">
          <div
            className="h-full bg-primary rounded-full transition-all duration-500 ease-out"
            style={{ width: `${percentage}%` }}
          />
        </div>

        {/* Stats */}
        <div className="flex justify-center gap-8 text-center">
          <div>
            <span className="font-mono text-3xl font-bold text-primary">
              {passing}
            </span>
            <span className="block text-sm text-muted-foreground uppercase">
              Passing
            </span>
          </div>
          <div className="text-4xl text-muted-foreground">/</div>
          <div>
            <span className="font-mono text-3xl font-bold">{total}</span>
            <span className="block text-sm text-muted-foreground uppercase">
              Total
            </span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
