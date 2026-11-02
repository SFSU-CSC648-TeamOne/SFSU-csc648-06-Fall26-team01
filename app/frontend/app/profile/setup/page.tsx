"use client";

import Navbar from "../../../components/Navbar";
import ProfileForm from "../../../components/ProfileForm";
import { useRequireAuth } from "../../../lib/auth";
import s from "../../screens.module.css";

export default function ProfileSetupPage() {
  const { user } = useRequireAuth();
  return (
    <main className={s.page}>
      <Navbar />
      <ProfileForm
        user={user}
        kicker="Step 2 of 2"
        title={<>Set up <span>your profile.</span></>}
        lead="Tell us your goal, level, schedule and equipment. You can change all of this later from Profile."
        submitLabel="Save profile"
      />
    </main>
  );
}
