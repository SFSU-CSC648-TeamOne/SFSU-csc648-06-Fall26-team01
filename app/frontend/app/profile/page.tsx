"use client";

import Navbar from "../../components/Navbar";
import ProfileForm from "../../components/ProfileForm";
import { displayName, useRequireAuth } from "../../lib/auth";
import s from "../screens.module.css";

export default function ProfilePage() {
  const { user } = useRequireAuth();
  return (
    <main className={s.page}>
      <Navbar />
      <ProfileForm
        user={user}
        kicker="Profile"
        title={<>{displayName(user) || "Your"} <span>profile.</span></>}
        lead="Update your goal, level, schedule and equipment. Changes apply to your next workouts."
        submitLabel="Save changes"
      />
    </main>
  );
}
