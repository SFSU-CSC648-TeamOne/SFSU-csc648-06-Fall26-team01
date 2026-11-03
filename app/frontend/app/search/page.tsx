
import styles from "./search.module.css";
import WorkoutMain from "../../components/WorkoutMain";

export default function SearchPage() {
  return (
    <main className={styles.page}>
      <section className={styles.heading}>
        <span className={styles.eyebrow}>
          07 — EXERCISE LIBRARY
        </span>

        <h1>
          EXPLORE
          <br />
          <span>EXERCISES.</span>
        </h1>

        <p>
          Find exercises based on your target muscle groups,
          available equipment, and training needs.
        </p>
      </section>

      <section className={styles.catalog}>
        <div className={styles.catalogHeader}>
          <div>
            <span className={styles.label}>DATABASE / EXERCISES</span>
            <h2>Exercise Catalog</h2>
          </div>

          <span className={styles.count}>ASCENDA LIBRARY</span>
        </div>

        <div className={styles.searchContent}>
          <WorkoutMain />
        </div>
      </section>
    </main>
  );
}
