
"use client";

import { Canvas } from "@react-three/fiber";
import { OrbitControls, useGLTF } from "@react-three/drei";
import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Box3, Vector3 } from "three";
import VideoPlane from "./VideoPlane";

const ROOM_URL = "/about/Scaniverse%202026-10-15%20121405.glb";
const VIDEOS = [
  { label: "Hercules Squat", url: "/about/demo_one.mp4" },
  { label: "Pistol Squat Jesus", url: "/about/demo_two.mp4" },
];

type RoomBounds = { width: number; height: number; depth: number };

function ScannedRoom({ onBounds }: { onBounds: (bounds: RoomBounds) => void }) {
  const { scene } = useGLTF(ROOM_URL);
  const info = useMemo(() => {
    // Center and normalize BOTH the video coordinates and GLB consistently.
    const box = new Box3().setFromObject(scene);
    const center = box.getCenter(new Vector3());
    const dimensions = box.getSize(new Vector3());
    const scale = 3.5 / Math.max(dimensions.x, dimensions.y, dimensions.z, 0.001);
    return {
      position: [-center.x * scale, -center.y * scale, -center.z * scale] as [number, number, number],
      scale,
      bounds: {
        width: dimensions.x * scale,
        height: dimensions.y * scale,
        depth: dimensions.z * scale,
      },
    };
  }, [scene]);

  useEffect(() => onBounds(info.bounds), [info, onBounds]);

  return (
    <group position={info.position} scale={info.scale}>
      <primitive object={scene} />
    </group>
  );
}

export default function ModelViewer() {
  const [selectedVideo, setSelectedVideo] = useState(VIDEOS[0].url);
  const [room, setRoom] = useState<RoomBounds>({ width: 3.5, height: 3, depth: 3 });
  const [offset, setOffset] = useState<[number, number, number]>([0, 0, 0.15]);
  const [status, setStatus] = useState("Loading 3D demonstration...");
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const onBounds = useCallback((bounds: RoomBounds) => setRoom(bounds), []);
  const onVideoChange = useCallback((video: HTMLVideoElement | null) => {
    videoRef.current = video;
  }, []);
  const onStatusChange = useCallback((message: string) => setStatus(message), []);

  // Normalize controls to fractions of the room dimensions so they work
  // irrespective of the actual Scaniverse GLB's imported scale.
  const position: [number, number, number] = [
    offset[0] * room.width,
    offset[1] * room.height,
    offset[2] * room.depth,
  ];
  const width = Math.min(2.3, Math.max(0.7, room.width * 0.45));

  function changeOffset(axis: number, value: number) {
    setOffset((current) => current.map((n, i) => i === axis ? value : n) as [number, number, number]);
  }

  async function playVideo() {
    try {
      await videoRef.current?.play();
      setStatus("Playing looping demonstration inside 3D scene");
    } catch {
      setStatus("Playback blocked or unsupported. Verify the MP4 codec.");
    }
  }

  return (
    <div style={{ width: "100%" }}>
      <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap", padding: "12px 16px" }}>
        <label htmlFor="ascenda-exercise-video" style={{ color: "#f4f1ea" }}>Exercise</label>
        <select
          id="ascenda-exercise-video"
          aria-label="Choose exercise demonstration"
          value={selectedVideo}
          onChange={(event) => setSelectedVideo(event.target.value)}
          style={{ padding: 8, background: "#252c37", color: "white" }}
        >
          {VIDEOS.map(({ label, url }) => <option key={url} value={url}>{label}</option>)}
        </select>
        <button type="button" onClick={() => void playVideo()} style={{ padding: "8px 14px" }}>Play</button>
        <button type="button" onClick={() => { videoRef.current?.pause(); setStatus("Video paused"); }} style={{ padding: "8px 14px" }}>Pause</button>
      </div>

      <div style={{ width: "100%", height: 520, background: "#10151e" }}>
        <Canvas camera={{ position: [0, 0.2, 5.5], fov: 48 }}>
          <ambientLight intensity={1.5} />
          <directionalLight position={[5, 5, 5]} intensity={2} />
          <Suspense fallback={null}>
            <ScannedRoom onBounds={onBounds} />
            <VideoPlane
              key={selectedVideo}
              src={selectedVideo}
              position={position}
              width={width}
              onVideoChange={onVideoChange}
              onStatusChange={onStatusChange}
            />
          </Suspense>
          <OrbitControls makeDefault enablePan={true} />
        </Canvas>
      </div>

      <div role="status" aria-live="polite" style={{ color: "#b5c2d5", padding: "8px 16px", fontSize: 13 }}>{status}</div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 14, padding: "8px 16px 16px", color: "#b5c2d5", fontSize: 12 }}>
        {(["Left / right", "Up / down", "Depth"] as const).map((label, axis) => (
          <label key={label} style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            {label}
            <input
              aria-label={`${label} video position`}
              type="range"
              min={-0.45}
              max={0.45}
              step={0.01}
              value={offset[axis]}
              onChange={(event) => changeOffset(axis, Number(event.target.value))}
            />
          </label>
        ))}
        <button type="button" onClick={() => setOffset([0, 0, 0.15])} style={{ padding: "6px 10px" }}>Reset position</button>
      </div>
    </div>
  );
}


/*******
  function Model() {
    const { scene } = useGLTF(
      "/about/Scaniverse%202026-10-15%20121405.glb"
    );

    return (
      <Center>
        <primitive object={scene} />
      </Center>
    );
  }

  export default function ModelViewer() {
    return (
      <div style={{ width: "100%", height: "440px" }}>
        <Canvas camera={{ position: [0, 0, 5], fov: 45 }}>
          <ambientLight intensity={1.5} />
          <directionalLight position={[5, 5, 5]} intensity={2} />
          <Suspense fallback={null}>
            <Model />
          </Suspense>
          <OrbitControls makeDefault />
        </Canvas>
      </div>
    );
  }
********/
