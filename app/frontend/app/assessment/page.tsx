
import Link from "next/link";

import Navbar from "../../components/Navbar";
import { PROGRAMS } from "../programs/programsData";
import s from "../screens.module.css";

export default function AssessmentPage() {
  return (
    <main className={s.page}>
      <Navbar />

      <div className={s.wrap}>
        <p className={s.kicker}>Program assessment</p>

        <h1 className={s.h1}>
          Establish your <span>baseline.</span>
        </h1>

        <p className={s.lead}>
          Choose a program to measure your starting performance.
          Your results will be used to personalize training.
        </p>

        <div className={s.list}>
          {PROGRAMS.map((program) => (
            <Link
              key={program.slug}
              href={`/assessment/${program.slug}`}
              className={s.row}
            >
              <span className={s.rowIdx}>
                {program.name}
              </span>

              <span className={s.rowTitle}>
                <strong>{program.fullName}</strong>
                <small>{program.tagline}</small>
              </span>

              <span className={s.tag}>ASSESS</span>
              <span aria-hidden="true">↗</span>
            </Link>
          ))}
        </div>
      </div>
    </main>
  );
}
