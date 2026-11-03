
"use client";

import { useEffect, useMemo, useState } from "react";

import { api } from "../../lib/auth";
import type { Program, ScheduledDay } from "./programsData";
import {
  personalizeSchedule,
  type ProgramBaseline,
} from "./prescription";

export function useProgramPrescription(
  program: Program,
  templateDays: ScheduledDay[],
  userId: number | null,
  authLoading: boolean
) {
  const [baseline, setBaseline] =
    useState<ProgramBaseline | null>(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (authLoading) return;

    if (userId === null) {
      setBaseline(null);
      setLoading(false);
      return;
    }

    let active = true;

    setLoading(true);
    setError("");
    setBaseline(null);

    api<ProgramBaseline | null>(
      `/program-baselines/latest?program=${program.slug}`
    )
      .then((record) => {
        if (active) setBaseline(record);
      })
      .catch((err) => {
        if (active) {
          setError(
            err instanceof Error
              ? err.message
              : "Could not load the assessment."
          );
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [program.slug, userId, authLoading]);

  const days = useMemo(
    () => personalizeSchedule(program, templateDays, baseline),
    [program, templateDays, baseline]
  );

  return { days, baseline, loading, error };
}
