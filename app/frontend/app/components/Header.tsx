import Link from "next/link";
import BrandIcon from "./BrandIcon";

export default function Header({ label, href }: { label: string; href: string }) {
  return (
    <header className="topbar">
      <div className="brand"><BrandIcon /><span>TeamProject</span></div>
      <Link className="topbar-link" href={href}>{label}</Link>
    </header>
  );
}
