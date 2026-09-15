# TeamProject

TeamProject is a fitness-focused application built by SFSU CSC 648 Team One. The
project is intended to provide helpful, personalized fitness experiences while
giving users a simple way to interact with the application.

The repository currently includes the shared About page and individual team
member pages. The backend directory is reserved for the Python and FastAPI
services that will support the application as development continues.

## Project Goals

- Build an approachable fitness application with personalized features.
- Use AI capabilities to provide helpful user experiences.
- Maintain a reliable data layer for application and user information.
- Practice collaborative development through GitHub branches, reviews, and merges.

## Technology Stack

```yaml
Cloud Hosting           : Vercel
Database                : Supabase, PostgreSQL
Front-end Framework     : React, JavaScript, TypeScript
Back-end Language       : Python
Back-end Framework      : FastAPI, ORM (SQLAlchemy)
Additional Technologies : TBD
IDE                     : Visual Studio Code
```

## Repository Structure

```text
app/
├── backend/                 # Backend services and API implementation
└── frontend/                # Frontend application and deployed About page
    ├── about/               # Team page and individual member profiles
    └── index.html            # Frontend entry point
.github/workflows/           # Deployment automation
milestones/                  # Course milestone deliverables
```

## Running the Frontend Locally

The current About page is made up of static frontend files. To preview it
locally, serve the frontend directory with a local web server:

```bash
cd app/frontend
python -m http.server 8000
```

Then open [http://localhost:8000](http://localhost:8000) in a browser. The
team page is available at [http://localhost:8000/about/](http://localhost:8000/about/).

## Deployment

The frontend is deployed through Vercel. GitHub Actions deploys changes to the
production site when a commit is pushed to `main` and includes frontend files.
The About page also has a dedicated deployment workflow for changes under
`app/frontend/about/`.

## Team Development Workflow

Team members should create a branch for their work, make focused commits, and
open a pull request for review. Approved changes are merged into `main`, which
serves as the deployable branch. This workflow keeps individual contributions
reviewable and helps the team coordinate frontend, backend, and documentation
updates.

## License

This project is licensed under the [MIT License](LICENSE).
