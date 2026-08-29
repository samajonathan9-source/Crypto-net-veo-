import { useMemo, useState } from "react";
import {
  Activity,
  ArrowUpRight,
  Binary,
  BookOpen,
  Check,
  ChevronDown,
  CircleHelp,
  Cpu,
  Fingerprint,
  KeyRound,
  LockKeyhole,
  Menu,
  Network,
  Search,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  TerminalSquare,
  X,
} from "lucide-react";

const algorithms = [
  { name: "AES-256-GCM", type: "Symmetric", status: "Recommended", score: 98, color: "cyan" },
  { name: "X25519", type: "Key exchange", status: "Modern", score: 96, color: "violet" },
  { name: "Ed25519", type: "Signature", status: "Modern", score: 95, color: "lime" },
  { name: "RSA-2048", type: "Asymmetric", status: "Legacy", score: 71, color: "amber" },
];

const activity = [
  ["Key rotation completed", "AES vault / production", "2m ago", "cyan"],
  ["New threat model created", "Post-quantum migration", "18m ago", "violet"],
  ["Benchmark finished", "UNSW-NB15 / 82,332 rows", "1h ago", "lime"],
];

function StatCard({ label, value, detail, icon: Icon, tone }: any) {
  return (
    <div className="stat-card">
      <div className={`stat-icon ${tone}`}><Icon size={18} /></div>
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
      <div className="stat-detail">{detail}</div>
    </div>
  );
}

export default function Home() {
  const [navOpen, setNavOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState("Overview");
  const [showAll, setShowAll] = useState(false);
  const filtered = useMemo(() => algorithms.filter((a) => a.name.toLowerCase().includes(query.toLowerCase())), [query]);

  return (
    <div className="app-shell">
      <aside className={`sidebar ${navOpen ? "open" : ""}`}>
        <div className="brand"><div className="brand-mark"><LockKeyhole size={19} /></div><div><strong>cipher<span>lab</span></strong><small>CRYPTO COMMAND</small></div><button className="close-nav" onClick={() => setNavOpen(false)}><X size={18}/></button></div>
        <div className="workspace"><span className="online-dot" /> Personal workspace <ChevronDown size={14} /></div>
        <nav>
          <div className="nav-kicker">Workspace</div>
          {["Overview", "Algorithms", "Key vault", "Threat models"].map((item, i) => <button key={item} onClick={() => { setSelected(item); setNavOpen(false); }} className={`nav-item ${selected === item ? "active" : ""}`}><span className="nav-symbol">{[<Activity size={16}/>, <Binary size={16}/>, <KeyRound size={16}/>, <ShieldCheck size={16}/>][i]}</span>{item}{item === "Threat models" && <span className="nav-count">3</span>}</button>)}
          <div className="nav-kicker second">Tools</div>
          {["Playground", "Documentation"].map((item, i) => <button key={item} onClick={() => setSelected(item)} className={`nav-item ${selected === item ? "active" : ""}`}><span className="nav-symbol">{i === 0 ? <TerminalSquare size={16}/> : <BookOpen size={16}/>}</span>{item}</button>)}
        </nav>
        <div className="sidebar-bottom"><div className="security-card"><div className="security-top"><span><Sparkles size={14}/> Security posture</span><b>GOOD</b></div><div className="posture-bar"><i /></div><p>Last scan 12 minutes ago</p></div><button className="profile"><div className="avatar">SJ</div><span><b>Sam Jonathan</b><small>Free workspace</small></span><ChevronDown size={15}/></button></div>
      </aside>
      {navOpen && <div className="overlay" onClick={() => setNavOpen(false)} />}
      <main className="main-content">
        <header className="topbar"><button className="menu-button" onClick={() => setNavOpen(true)}><Menu size={20}/></button><div className="breadcrumbs"><span>Workspace</span><span>/</span><b>{selected}</b></div><div className="top-actions"><div className="command-hint"><Search size={15}/><input aria-label="Search algorithms" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search algorithms..."/><kbd>⌘ K</kbd></div><button className="icon-button"><CircleHelp size={18}/></button><div className="top-avatar">SJ</div></div></header>
        <div className="page-wrap">
          <section className="hero"><div><div className="eyebrow"><span className="pulse" /> SYSTEM ONLINE <span className="eyebrow-divider" /> 29 AUG 2026</div><h1>Cryptography,<br/><em>made legible.</em></h1><p>One clear surface for stronger keys, safer protocols,<br className="desktop"/> and a calmer security posture.</p></div><div className="hero-orbit"><div className="orbit orbit-one"/><div className="orbit orbit-two"/><div className="orbit-core"><Fingerprint size={37}/><span>256</span></div><div className="orbit-label label-top">ENCRYPTED</div><div className="orbit-label label-right">AES-GCM</div><div className="orbit-label label-bottom">QUANTUM READY</div></div></section>
          <section className="stats-grid"><StatCard label="Active keys" value="24" detail="+4 this month" icon={KeyRound} tone="cyan"/><StatCard label="Security score" value="92.8" detail="↑ 4.6% vs last scan" icon={ShieldCheck} tone="lime"/><StatCard label="Algorithms tracked" value="18" detail="4 need review" icon={Binary} tone="violet"/><StatCard label="Threats mitigated" value="1,284" detail="This workspace" icon={Network} tone="amber"/></section>
          <section className="content-grid"><div className="panel algorithms-panel"><div className="panel-head"><div><div className="section-eyebrow">ALGORITHM REGISTRY</div><h2>Core algorithms</h2></div><button className="text-button" onClick={() => setShowAll(!showAll)}>{showAll ? "Collapse" : "View registry"}<ArrowUpRight size={15}/></button></div><div className="table-head"><span>Algorithm</span><span>Type</span><span>Posture</span><span>Score</span></div>{(showAll ? [...filtered, ...filtered] : filtered).map((a, i) => <div className="algorithm-row" key={`${a.name}-${i}`}><div className={`algo-icon ${a.color}`}>{a.name.startsWith("AES") ? <LockKeyhole size={16}/> : a.name.startsWith("X") ? <Network size={16}/> : a.name.startsWith("Ed") ? <Fingerprint size={16}/> : <KeyRound size={16}/>}</div><div className="algo-name"><b>{a.name}</b><small>Verified library</small></div><div className="algo-type">{a.type}</div><div><span className={`status ${a.color}`}><Check size={11}/> {a.status}</span></div><div className="score"><b>{a.score}</b><div className="mini-bar"><i style={{width: `${a.score}%`}} /></div></div></div>)}</div>
          <div className="right-stack"><div className="panel activity-panel"><div className="panel-head"><div><div className="section-eyebrow">LIVE FEED</div><h2>Recent activity</h2></div><button className="dots">•••</button></div><div className="activity-list">{activity.map(([title, sub, time, tone]) => <div className="activity-item" key={title}><div className={`activity-icon ${tone}`}>{tone === "cyan" ? <KeyRound size={15}/> : tone === "violet" ? <ShieldCheck size={15}/> : <Activity size={15}/>}</div><div><b>{title}</b><small>{sub}</small></div><time>{time}</time></div>)}</div><button className="activity-link">View audit log <ArrowUpRight size={14}/></button></div><div className="panel quick-panel"><div className="quick-icon"><SlidersHorizontal size={19}/></div><div><div className="section-eyebrow">QUICK ACTION</div><h3>Run a security scan</h3><p>Check your active keys and protocols against current best practices.</p></div><button className="scan-button" onClick={() => alert("Scan queued — your workspace is already in good shape.")}>Scan now <ArrowUpRight size={15}/></button></div></div></section>
          <footer><span><span className="online-dot" /> All systems operational</span><span>Last synced just now</span><span className="footer-version">cipherlab v0.8.4</span></footer>
        </div>
      </main>
    </div>
  );
}
