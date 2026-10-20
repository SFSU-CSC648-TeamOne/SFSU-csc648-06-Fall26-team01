import WorkoutMain from "../../components/WorkoutMain";

export default function SearchPage() {
  return (
    <main className="site">
      <section className="catalog" id="search">
        <div className="catalog-copy">
          <span className="section-number">SEARCH / WORKOUTS</span>

          <h1>
            FIND THE
            <br />
            <span>RIGHT WORKOUT.</span>
          </h1>

          <p>
            Search and filter database-backed workouts by exercise, muscle
            group, difficulty, and duration.
          </p>
        </div>

        <div className="catalog-ui">
          <WorkoutMain />
        </div>
      </section>
    </main>
  );
}
