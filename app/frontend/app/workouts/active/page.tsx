import { Suspense } from "react";
import ActiveWorkout from "./ActiveWorkout";

export default function ActiveWorkoutPage() {
  return <Suspense fallback={null}><ActiveWorkout /></Suspense>;
}
