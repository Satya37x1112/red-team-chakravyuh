import { useState } from "react";
import { HistoryFilter, HistoryTable } from "../components/HistoryTable";
import { Button, Icon, Panel } from "../components/ui";
import { useLiveContext } from "../live-context";
import type { Kind } from "../types";

export function History() {
  const { analytics, refreshAnalytics } = useLiveContext();
  const [filter, setFilter] = useState<"all" | Kind>("all");
  return (
    <div className="flex flex-col gap-5">
      <div>
        <h1 className="text-[22px] font-semibold tracking-tight text-ink">Execution history</h1>
        <p className="mt-1 text-xs text-muted">Every authorized session persisted to the audit log, newest first.</p>
      </div>
      <Panel
        title={`${analytics.length} sessions`}
        actions={
          <>
            <HistoryFilter value={filter} onChange={setFilter} />
            <Button onClick={refreshAnalytics} title="Reload from the database">
              <Icon name="refresh" size={13} />
            </Button>
          </>
        }
        bodyClass="pt-3"
      >
        <HistoryTable rows={analytics} filter={filter} />
      </Panel>
    </div>
  );
}
