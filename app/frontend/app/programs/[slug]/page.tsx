import { notFound } from "next/navigation";
import { PROGRAMS, getProgram, buildSchedule } from "../programsData";
import ProgramView from "./ProgramView";

export function generateStaticParams() {
  return PROGRAMS.map((p) => ({ slug: p.slug }));
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const program = getProgram(slug);
  return { title: program ? `${program.fullName} | Ascenda` : "Program | Ascenda" };
}

export default async function ProgramPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const program = getProgram(slug);
  if (!program) notFound();
  return <ProgramView program={program} days={buildSchedule(program)} />;
}
