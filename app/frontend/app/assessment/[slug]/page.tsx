
"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import Navbar from "../../../components/Navbar";
import { api, useRequireAuth } from "../../../lib/auth";
import { getProgram } from "../../programs/programsData";
import s from "../../screens.module.css";

type Test = {
  id: string;
  name: string;
  metric: "reps" | "seconds";
  weighted: boolean;
};

type Result = {
  exercise_id: string;
  value: number;
  load_kg: number | null;
};

type Baseline = {
  id: number;
  program_slug: string;
  attempt_id: string;
  results: Result[];
  created_at: string;
};

type FormResult = {
  value: string;
  load_kg: string;
};

export default function ProgramAssessmentPage() {
  const { slug } = useParams<{ slug: string }>();
  const { user, loading: authLoading } = useRequireAuth();

  const program = getProgram(slug);

  const [tests, setTests] = useState<Test[]>([]);
  const [values, setValues] = useState<Record<string, FormResult>>({});
  const [previous, setPrevious] = useState<Baseline | null>(null);
  const [saved, setSaved] = useState<Baseline | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (authLoading || !user || !program) return;

    setLoading(true);
    setSaved(null);
    setError("");

    Promise.all([
      api<Test[]>(`/program-baselines/tests?program=${slug}`),
      api<Baseline | null>(
        `/program-baselines/latest?program=${slug}`
      ),
    ])
      .then(([testList, latest]) => {
        setTests(testList);
        setPrevious(latest);
      })
      .catch((err) => {
        setError(
          err instanceof Error
            ? err.message
            : "Unable to load assessment."
        );
      })
      .finally(() => setLoading(false));
  }, [authLoading, user?.id, slug, program?.slug]);

  function update(
    exerciseId: string,
    field: keyof FormResult,
    value: string
  ) {
    setValues((current) => ({
      ...current,
      [exerciseId]: {
        value: current[exerciseId]?.value ?? "",
        load_kg: current[exerciseId]?.load_kg ?? "",
        [field]: value,
      },
    }));
  }

  const complete =
    tests.length > 0 &&
    tests.every((test) => {
      const entry = values[test.id];
      if (!entry) return false;

      const number = Number(entry.value);

      if (
        entry.value.trim() === "" ||
        !Number.isInteger(number) ||
        number < 0 ||
        number > 10000
      ) {
        return false;
      }

      if (test.weighted) {
        const load = Number(entry.load_kg);

        return (
          entry.load_kg.trim() !== "" &&
          Number.isFinite(load) &&
          load >= 0 &&
          load <= 1000
        );
      }

      return true;
    });

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!complete || saving || !program) return;

    setSaving(true);
    setError("");

    const results: Result[] = tests.map((test) => ({
      exercise_id: test.id,
      value: Number(values[test.id].value),
      load_kg: test.weighted
        ? Number(values[test.id].load_kg)
        : null,
    }));

    try {
      const record = await api<Baseline>("/program-baselines", {
        method: "POST",
        body: JSON.stringify({
          program_slug: program.slug,
          results,
        }),
      });

      setSaved(record);
      setPrevious(record);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Failed to save baseline."
      );
    } finally {
      setSaving(false);
    }
  }

  if (!program) {
    return (
      <main className={s.page}>
        <Navbar />
        <div className={s.wrap}>
          <h1>Program not found.</h1>
          <Link href="/assessment" className={s.btn}>
            Select program
          </Link>
        </div>
      </main>
    );
  }

  if (authLoading || !user) {
    return (
      <main className={s.page}>
        <Navbar />
        <div className={s.wrap}>Checking account...</div>
      </main>
    );
  }

  return (
    <main className={s.page}>
      <Navbar />

      <div className={`${s.wrap} ${s.narrow}`}>
        <Link href="/assessment" className={s.muted}>
          ← All assessments
        </Link>

        <p className={s.kicker} style={{ marginTop: 28 }}>
          Initial assessment / {program.name}
        </p>

        <h1 className={s.h1}>
          Your starting <span>point.</span>
        </h1>

        <p className={s.lead}>
          {program.fullName}. Complete each test with controlled
          technique and record your actual performance.
        </p>

        {error && (
          <p className={s.error} role="alert">
            {error}
          </p>
        )}

        {saved ? (
          <section className={s.card}>
            <p className={s.kicker}>Baseline saved</p>

            <h2>Assessment complete</h2>

            {saved.results.map((result) => {
              const test = tests.find(
                (item) => item.id === result.exercise_id
              );

              return (
                <p key={result.exercise_id}>
                  <strong>{test?.name ?? result.exercise_id}</strong>
                  {" — "}
                  {result.value} {test?.metric ?? "reps"}
                  {result.load_kg !== null &&
                    ` at ${result.load_kg} kg`}
                </p>
              );
            })}

            <p className={s.muted}>
              Your baseline has been saved. Personalized sets and
              reps will be connected in the next implementation section.
            </p>

            <div className={s.actions}>
              <Link
                href={`/programs/${program.slug}`}
                className={s.btn}
              >
                View program ↗
              </Link>

              <Link
                href="/profile"
                className={`${s.btn} ${s.btnGhost}`}
              >
                Profile
              </Link>
            </div>
          </section>
        ) : loading ? (
          <p className={s.muted}>Loading assessment...</p>
        ) : previous ? (
          <section className={s.card}>
            <p className={s.kicker}>Existing baseline</p>

            <h2>Starting point recorded</h2>

            <p className={s.muted}>
              You have already completed an initial assessment
              for this program.
            </p>

            <div className={s.list}>
              {previous.results.map((result) => {
                const test = tests.find(
                  (item) => item.id === result.exercise_id
                );

                return (
                  <div key={result.exercise_id} className={s.row}>
                    <span className={s.rowTitle}>
                      <strong>
                        {test?.name ?? result.exercise_id}
                      </strong>
                      <small>
                        {result.value} {test?.metric ?? "reps"}
                        {result.load_kg !== null &&
                          ` at ${result.load_kg} kg`}
                      </small>
                    </span>
                  </div>
                );
              })}
            </div>

            <div className={s.actions}>
              <Link
                href={`/programs/${program.slug}`}
                className={s.btn}
              >
                View program ↗
              </Link>

              <button
                type="button"
                className={`${s.btn} ${s.btnGhost}`}
                onClick={() => {
                  setPrevious(null);
                  setValues({});
                }}
              >
                Start another attempt
              </button>
            </div>
          </section>
        ) : (
          <form className={s.form} onSubmit={submit}>
            {tests.map((test, index) => (
              <section key={test.id} className={s.card}>
                <p className={s.kicker}>
                  Test {String(index + 1).padStart(2, "0")}
                </p>

                <h2>{test.name}</h2>

                <div className={s.field}>
                  <label htmlFor={`${test.id}-value`}>
                    {test.metric === "seconds"
                      ? "Hold duration (seconds)"
                      : "Completed repetitions"}
                  </label>

                  <input
                    id={`${test.id}-value`}
                    type="number"
                    className={s.input}
                    min={0}
                    max={10000}
                    step={1}
                    required
                    value={values[test.id]?.value ?? ""}
                    onChange={(event) =>
                      update(
                        test.id,
                        "value",
                        event.target.value
                      )
                    }
                  />
                </div>

                {test.weighted && (
                  <div
                    className={s.field}
                    style={{ marginTop: 16 }}
                  >
                    <label htmlFor={`${test.id}-load`}>
                      Load used (kg)
                    </label>

                    <input
                      id={`${test.id}-load`}
                      type="number"
                      className={s.input}
                      min={0}
                      max={1000}
                      step="any"
                      required
                      value={values[test.id]?.load_kg ?? ""}
                      onChange={(event) =>
                        update(
                          test.id,
                          "load_kg",
                          event.target.value
                        )
                      }
                    />
                  </div>
                )}
              </section>
            ))}

            <button
              type="submit"
              className={s.btn}
              disabled={!complete || saving}
            >
              {saving ? "Saving..." : "Save initial assessment ↗"}
            </button>
          </form>
        )}
      </div>
    </main>
  );
}
