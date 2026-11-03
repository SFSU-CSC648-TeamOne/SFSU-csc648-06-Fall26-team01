
"use client";

import { Canvas } from "@react-three/fiber";
import { OrbitControls, useGLTF } from "@react-three/drei";
import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Box3, Vector3 } from "three";
import VideoPlane from "./VideoPlane";
import AnimatedDummy from "./AnimatedDummy";

const ROOM_URL = "/about/Scaniverse%202026-10-15%20121405.glb";

// glb + clip = 3D dummy (names are case sensitive)
// video = optional 2D video (leave undefined when there is none)
const DEMOS = [
  { label: "Hercules Squat", glb: "/about/Hercules_Squat.glb", clip: "Hercules_Squat", video: "/about/demo_one.mp4" },
  { label: "Pistol Squat", glb: "/about/Pistol_Squat.glb", clip: "Pistol_Squat", video: "/about/demo_two.mp4" },
  { label: "Push-Up", glb: "/about/Push_up.glb", clip: "Push_up", video: undefined as string | undefined },
];

type RoomBounds = { width: number; height: number; depth: number; scale: number };

function ScannedRoom({ onBounds }: { onBounds: (bounds: RoomBounds) => void }) {
  const { scene } = useGLTF(ROOM_URL);
  const info = useMemo(() => {
    // center and normalize BOTH the video coordinates and glb consistently
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
        scale, // AnimatedDummy needs this to size the dummy to the room
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
  const [demoIndex, setDemoIndex] = useState(0);
  const [show3D, setShow3D] = useState(true); // true = 3D dummy, false = 2D video
  const [playing, setPlaying] = useState(true);
  const [room, setRoom] = useState<RoomBounds>({ width: 3.5, height: 3, depth: 3, scale: 1 });
  const [offset, setOffset] = useState<[number, number, number]>([0, 0, 0.15]);
  const [status, setStatus] = useState("Loading 3D demonstration...");
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const onBounds = useCallback((bounds: RoomBounds) => setRoom(bounds), []);
  const onVideoChange = useCallback((video: HTMLVideoElement | null) => {
    videoRef.current = video;
  }, []);
  const onStatusChange = useCallback((message: string) => setStatus(message), []);

  const demo = DEMOS[demoIndex];
  const dummyOn = show3D || !demo.video; // demos with no video are always 3D

  // normalize controls to fractions of the room dimensions so they work
  // with Scaniverse GLB's imported scale
  const position: [number, number, number] = [
    offset[0] * room.width,
    offset[1] * room.height,
    offset[2] * room.depth,
  ];

  const width = Math.min(2.3, Math.max(0.7, room.width * 0.45));
  
  // The room is centered at the origin, so -height/2 is the floor of the scan.
  const feet: [number, number, number] = [position[0], -room.height / 2 + position[1], position[2]];

  function changeOffset(axis: number, value: number) {
    setOffset((current) => current.map((n, i) => i === axis ? value : n) as [number, number, number]);
  }

  async function play() {
    if (dummyOn) {
      setPlaying(true);
      setStatus(`Playing 3D demonstration: ${demo.label}`);
      return;
    }
    try {
      await videoRef.current?.play();
      setStatus("Playing looping demonstration inside 3D scene");
    } catch {
      setStatus("Playback blocked or unsupported. Verify the MP4 codec.");
    }
  }

  function pause() {
    if (dummyOn) setPlaying(false);
    else videoRef.current?.pause();
    setStatus("Paused");
  }

  return (
    <div style={{ width: "100%" }}>
      <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap", padding: "12px 16px" }}>
        <label htmlFor="ascenda-exercise-video" style={{ color: "#f4f1ea" }}>Exercise</label>
        <select
          id="ascenda-exercise-video"
          aria-label="Choose exercise demonstration"
          value={demoIndex}
          onChange={(event) => { setDemoIndex(Number(event.target.value)); setPlaying(true); }}
          style={{ padding: 8, background: "#252c37", color: "white" }}
        >
          {DEMOS.map(({ label }, index) => <option key={label} value={index}>{label}</option>)}
        </select>
        <button type="button" onClick={() => void play()} style={{ padding: "8px 14px" }}>Play</button>
        <button type="button" onClick={pause} style={{ padding: "8px 14px" }}>Pause</button>
        <button type="button" disabled={!demo.video} onClick={() => setShow3D(!show3D)} style={{ padding: "8px 14px" }}>
          {dummyOn ? "Show 2D video" : "Show 3D dummy"}
        </button>
      </div>

      <div style={{ width: "100%", height: 520, background: "#10151e" }}>
        <Canvas camera={{ position: [0, 0.2, 5.5], fov: 48 }}>
          <ambientLight intensity={1.5} />
          <directionalLight position={[5, 5, 5]} intensity={2} />
          <Suspense fallback={null}>
            <ScannedRoom onBounds={onBounds} />
            {dummyOn ? (
              <AnimatedDummy
                key={demo.glb}
                url={demo.glb}
                animationName={demo.clip}
                position={feet}
                roomScale={room.scale}
                heightMeters={1.8}
                playing={playing}
              />
            ) : (
              <VideoPlane
                key={demo.video}
                src={demo.video!}
                position={position}
                width={width}
                onVideoChange={onVideoChange}
                onStatusChange={onStatusChange}
              />
            )}
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