// adds data fields for KinemIQ 3D videos as an overlay
// and adds a new page for the 3D space 

"use client";

import { useEffect, useMemo, useRef } from "react";
import { useGLTF, useAnimations } from "@react-three/drei";
import { Box3, Group, Vector3 } from "three";
import { clone } from "three/examples/jsm/utils/SkeletonUtils.js";

// data value set up
type Props = {
    url: string; // location of .glb video
    position: [number, number, number]; // position of the dummmy's feet
    roomScale: number; // scanning units
    heightMeters?: number; // height of the dummy
    rotationY?: number; // rotation of the dummy
    animationName?: string; // name of the video to play
    playing?: boolean; // is video playing?
};

export default function AnimationDummy({
    url,
    position,
    roomScale,
    heightMeters = 1.8,
    rotationY = 0,
    animationName,
    playing = true,
}: Props) {
    const root = useRef<Group>(null);
    const { scene, animations } = useGLTF(url);

    // clones the model in the .glb file so it is 
    // safe to reuse and animate multiple timmes
    const model = useMemo(() => clone(scene), [scene]);

    // calculates the sie of the model and puts it's
    // feet at the y=0 position
    const fit = useMemo(() => {
        model.updateMatrixWorld(true);
        const box = new Box3().setFromObject(model);
        const size = box.getSize(new Vector3());
        const center = box.getCenter(new Vector3());
        return {
            scale: (heightMeters * roomScale) / Math.max(size.y, 0.001),
            offset: [-center.x, -box.min.y, -center.z] as [number, number, number],
        };
    }, [model, heightMeters, roomScale]);

    const { actions, names } = useAnimations(animations, root);

    // starting the animation (video starts by default)
    useEffect(() => {
    console.log(`Dummy animations: ${names.length}`, names);
    const action = actions[animationName ?? names[0]];

    if (!action) return;
    action.reset().play();
    return () => {
        action.stop();
    };
    }, [actions, names, animationName]);

    // pause and resuming animation
    useEffect(() => {
    const action = actions[animationName ?? names[0]];
    if (action) action.paused = !playing;
    }, [actions, names, animationName, playing]);

    return (
    <group position={position} rotation={[0, rotationY, 0]}>
        <group scale={fit.scale}>
        <group ref={root} position={fit.offset}>
            <primitive object={model} />
        </group>
        </group>
    </group>
    );
}
