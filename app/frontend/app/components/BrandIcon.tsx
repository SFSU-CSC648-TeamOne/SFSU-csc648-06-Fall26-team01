export default function BrandIcon() {
  return (
    <svg className="brand-icon" viewBox="0 0 48 48" role="img" aria-label="Fitness and AI">
      <circle cx="24" cy="24" r="21" fill="#1681f5" />
      <path d="M24 10 L17 17 M24 10 L31 17 M17 17 H31" fill="none" stroke="#ffb72d" strokeWidth="2" strokeLinecap="round" />
      <circle cx="24" cy="10" r="3" fill="#ffb72d" />
      <circle cx="17" cy="17" r="3" fill="#ffb72d" />
      <circle cx="31" cy="17" r="3" fill="#ffb72d" />
      <path d="M17 27 H31" stroke="white" strokeWidth="4" strokeLinecap="round" />
      <path d="M12 22 V32 M16 20 V34 M32 20 V34 M36 22 V32" stroke="white" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}
