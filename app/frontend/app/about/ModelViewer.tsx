
"use client";

import { Canvas } from "@react-three/fiber";
import { Center, OrbitControls, useGLTF } from "@react-three/drei";
import { Suspense } from "react";

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
