"use client";

import { Canvas } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import { Suspense } from "react";
import AnimatedDummy from "../app/about/AnimatedDummy";

export default function DummyViewer({ url, clip }: { url: string; clip?: string }) {
  return (
    <div style={{ width: "100%", aspectRatio: "4 / 3" }}>
      <Canvas camera={{ position: [0, 1.3, 3.4], fov: 45 }}>
        <ambientLight intensity={0.9} />
        <directionalLight position={[3, 5, 2]} intensity={1.4} />
        <Suspense fallback={null}>
          <AnimatedDummy
            url={url}
            position={[0, 0, 0]}
            roomScale={1}
            animationName={clip}
            playing
          />
        </Suspense>
        <OrbitControls target={[0, 0.9, 0]} enablePan={false} />
      </Canvas>
    </div>
  );
}