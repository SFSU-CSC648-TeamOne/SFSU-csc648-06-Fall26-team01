"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { use, useEffect, useState } from "react";
import Navbar from "../../../components/Navbar";
import { api } from "../../../lib/auth";
import s from "../../screens.module.css";

const ScanViewer = dynamic(() => import("../../../components/ScanViewer"), { ssr: false, loading: () => <div className={s.scanBox}>Loading 3D scan...</div> });

type Exercise = { id: number; name: string; description?: string | null; primary_muscles?: string[]; equipment?: string[] };
type Model = { model_url?: string | null; video_url?: string | null };
// Posture scans: one row per key position (for example push-up top and bottom). Needs GET /api/exercises/{id}/scans.
type Scan = { position: number; label: string; description?: string | null; model_url?: string | null };

export default function ExercisePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [ex, setEx] = useState<Exercise | null>(null);
  const [model, setModel] = useState<Model>({});
  const [scans, setScans] = useState<Scan[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    api<Exercise>(`/exercises/${id}`).then(setEx).catch((e) => setError(e.message));
    api<Model>(`/exercises/${id}/model`).then(setModel).catch(() => {});
    api<Scan[]>(`/exercises/${id}/scans`).then((r) => setScans([...r].sort((a, b) => a.position - b.position))).catch(() => {});
  }, [id]);

  const slots: (Scan | null)[] = [scans[0] ?? null, scans[1] ?? null];

  return (
    <main className={s.page}>
      <Navbar />
      <div className={s.wrap}>
        <p className={s.kicker}>{ex?.primary_muscles?.join(" · ") || "Exercise"}</p>
        <h1 className={s.h1}>Explore the <span>movement.</span></h1>
        {error && <p className={s.error}>{error}</p>}

        <div className={s.exGrid}>
          {/* Left: 3D video, name, description, add to workout */}
          <div>
            <div className={s.scan}>
              <div className={s.scanTop}><span>3D VIDEO</span><span>{model.video_url ? "PLAYING IN GYM SCAN" : "NOT UPLOADED YET"}</span></div>
              {model.video_url
                ? <video className={s.video} src={model.video_url} controls playsInline preload="metadata" />
                : <div className={s.scanBox}>The 3D demonstration video for this exercise is not uploaded yet.</div>}
            </div>
            <h2 style={{ fontSize: 28, margin: "22px 0 8px", textTransform: "uppercase" }}>{ex?.name}</h2>
            <p className={s.lead} style={{ marginBottom: 18 }}>{ex?.description || "No description yet."}</p>
            {/* TODO: no backend for a custom workout exists yet, so this opens Programs to pick a session. */}
            <Link href="/programs" className={`${s.btn} ${s.btnGreen}`}>Add to workout</Link>
          </div>

          {/* Right: two rotatable Niantic posture scans */}
          <div className={s.scanGrid} style={{ alignContent: "start" }}>
            {slots.map((sc, i) => (
              <div className={s.scan} key={i}>
                <div className={s.scanTop}><span>NIANTIC 3D SCAN</span><span>DRAG TO ROTATE</span></div>
                {sc?.model_url ? <ScanViewer url={sc.model_url} /> : <div className={s.scanBox}>Posture scan {i + 1} is not uploaded yet.</div>}
                <div className={s.scanCap}><b>{i + 1}  {sc?.label ?? (i === 0 ? "Top position" : "Bottom position")}</b><small>{sc?.description ?? ""}</small></div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </main>
  );
}
