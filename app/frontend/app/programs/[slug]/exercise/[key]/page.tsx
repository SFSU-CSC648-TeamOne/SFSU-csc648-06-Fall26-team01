import { notFound } from "next/navigation";
import { getProgram } from "../../../programsData";
import ExerciseWorkout from "./ExerciseWorkout";

export const metadata = { title: "Exercise | Ascenda" };

export default async function ExercisePage({ params }: { params: Promise<{ slug: string; key: string }> }) {
  const { slug, key } = await params;
  if (!getProgram(slug)) notFound();
  return <ExerciseWorkout slug={slug} exKey={decodeURIComponent(key)} />;
}
