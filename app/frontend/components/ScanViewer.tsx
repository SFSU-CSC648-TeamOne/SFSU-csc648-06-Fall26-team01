"use client";

import { Canvas } from "@react-three/fiber";
import { Bounds, Center, OrbitControls, useGLTF } from "@react-three/drei";
import { Component, Suspense, type ReactNode } from "react";

function Model({ url }: { url: string }) {
  const { scene } = useGLTF(url);
  return <Center><primitive object={scene} /></Center>;
}

/** Rotatable 3D scan (GLB). Drag to rotate, scroll to zoom. */
function Viewer({ url }: { url: string }) {
  return (
    <Canvas camera={{ position: [2, 1.5, 3], fov: 45 }} style={{ height: 240, background: "#0c0e12" }}>
      <ambientLight intensity={1.1} />
      <directionalLight position={[3, 5, 2]} intensity={1.4} />
      <Suspense fallback={null}>
        <Bounds fit clip observe margin={1.25}><Model url={url} /></Bounds>
      </Suspense>
      <OrbitControls enablePan={false} makeDefault />
    </Canvas>
  );
}

/** A missing or broken .glb file must not take the whole page down: show a message instead. */
class Boundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  render() {
    return this.state.failed
      ? <div style={{ height: 240, display: "grid", placeItems: "center", color: "#8e98a8", fontSize: 13, textAlign: "center", padding: 12 }}>Could not load this 3D scan file.</div>
      : this.props.children;
  }
}

export default function ScanViewer({ url }: { url: string }) {
  return <Boundary key={url}><Viewer url={url} /></Boundary>;
}
