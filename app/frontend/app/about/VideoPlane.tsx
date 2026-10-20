"use client";

import { useEffect, useState } from "react";
import { DoubleSide, SRGBColorSpace, VideoTexture } from "three";

type VideoPlaneProps = {
  src: string;
  position: [number, number, number];
  width: number;
  onVideoChange: (video: HTMLVideoElement | null) => void;
  onStatusChange: (message: string) => void;
};

/** A real 3D mesh: its texture updates as the HTML video plays. */
export default function VideoPlane({
  src,
  position,
  width,
  onVideoChange,
  onStatusChange,
}: VideoPlaneProps) {
  const [texture, setTexture] = useState<VideoTexture | null>(null);
  const [aspectRatio, setAspectRatio] = useState(16 / 9);

  useEffect(() => {
    const video = document.createElement("video");
    video.src = src;
    video.preload = "auto";
    video.crossOrigin = "anonymous";
    video.muted = true; // Required for reliable browser autoplay.
    video.defaultMuted = true;
    video.loop = true;
    video.playsInline = true;

    const videoTexture = new VideoTexture(video);
    videoTexture.colorSpace = SRGBColorSpace;
    let active = true;

    const metadata = () => {
      if (active && video.videoWidth && video.videoHeight) {
        setAspectRatio(video.videoWidth / video.videoHeight);
      }
    };
    const failed = () => {
      if (active) onStatusChange("Unable to load video. Check the MP4 path and codec.");
    };
    video.addEventListener("loadedmetadata", metadata);
    video.addEventListener("error", failed);
    onVideoChange(video);
    setTexture(videoTexture);
    setAspectRatio(16 / 9);
    onStatusChange("Loading exercise demonstration...");

    // A muted looping video can normally autoplay. The viewer provides a
    // user-gesture Play control for browsers that still block it.
    void video.play().then(() => {
      if (active) onStatusChange("Playing looping demonstration inside 3D scene");
    }).catch(() => {
      if (active) onStatusChange("Select Play to start the demonstration");
    });

    return () => {
      active = false;
      onVideoChange(null);
      video.removeEventListener("loadedmetadata", metadata);
      video.removeEventListener("error", failed);
      video.pause();
      video.removeAttribute("src");
      video.load();
      videoTexture.dispose();
    };
  }, [src, onVideoChange, onStatusChange]);

  if (!texture) return null;

  return (
    <mesh position={position}>
      <planeGeometry args={[width, width / aspectRatio]} />
      <meshBasicMaterial
        map={texture}
        side={DoubleSide}
        toneMapped={false}
        depthTest={true}
        depthWrite={false}
      />
    </mesh>
  );
}
