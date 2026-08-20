import radarData from "../../public/data/opportunity-radar.json";
import researchQueue from "../../public/data/opportunity-research-queue.json";

const lanes = [
  { name: "EDGE", meaning: "Weak signals before the market fully confirms them", state: "Discovery" },
  { name: "CATALYST", meaning: "Known event with a measurable timing window", state: "Clock" },
  { name: "QUANT", meaning: "Price/pop/liquidity dislocation visible in the data", state: "Measure" },
];

const formatObserved = (value: string) => new Intl.DateTimeFormat("en-US", {
  month: "short", day: "numeric", hour: "numeric", minute: "2-digit", timeZone: "America/Phoenix", timeZoneName: "short",
}).format(new Date(value));
const formatWindow = (value: string) => new Intl.DateTimeFormat("en-US", {
  month: "short", day: "numeric", timeZone: "UTC",
}).format(new Date(value));

export default function RadarPage() {
  const candidates = radarData.candidates;
  const queue = researchQueue.items;
  return <main style={{maxWidth:1120,margin:"0 auto",padding:"28px 18px 80px",fontFamily:"system-ui,-apple-system,sans-serif",color:"#f4f4f5",background:"#09090b",minHeight:"100vh"}}>
    <nav style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:48}}>
      <a href="../" style={{color:"#f4f4f5",textDecoration:"none",fontWeight:800}}>MARKET OS</a>
      <span style={{fontSize:12,color:"#a1a1aa",letterSpacing:1.5}}>OPPORTUNITY ENGINE · ALPHA</span>
    </nav>

    <section style={{marginBottom:34}}>
      <div style={{fontSize:12,color:"#a1a1aa",letterSpacing:1.5,marginBottom:10}}>RADAR · {candidates.length} LIVE WATCHES</div>
      <h1 style={{fontSize:"clamp(38px,8vw,72px)",lineHeight:.95,letterSpacing:-3,margin:"0 0 18px"}}>Find the move<br/>before consensus.</h1>
      <p style={{maxWidth:760,color:"#a1a1aa",fontSize:17,lineHeight:1.6}}>These are real, timestamped Opportunity Engine candidates already preserved in the repository. None is a buy yet: every card remains locked until authoritative eBay Product Research comps verify whether the hobby has already repriced the catalyst.</p>
    </section>

    <section style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(220px,1fr))",gap:12,marginBottom:34}}>
      {lanes.map(lane => <article key={lane.name} style={{border:"1px solid #27272a",borderRadius:16,padding:20,background:"#111113"}}><div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:30}}><b>{lane.name}</b><span style={{fontSize:11,border:"1px solid #3f3f46",borderRadius:999,padding:"5px 8px",color:"#a1a1aa"}}>{lane.state}</span></div><p style={{color:"#a1a1aa",lineHeight:1.5,margin:0}}>{lane.meaning}</p></article>)}
    </section>

    <section style={{border:"1px solid #27272a",borderRadius:18,overflow:"hidden",background:"#111113"}}>
      <div style={{padding:20,borderBottom:"1px solid #27272a",display:"flex",justifyContent:"space-between",gap:20,alignItems:"center"}}><div><div style={{fontSize:12,color:"#a1a1aa",letterSpacing:1.3}}>ACTIVE RADAR</div><h2 style={{margin:"5px 0 0",fontSize:24}}>Candidate queue</h2></div><span style={{fontSize:12,color:"#fbbf24"}}>WATCH FOR COMPS</span></div>
      <div>
        {candidates.map((candidate, index) => <article key={candidate.player_id} style={{padding:20,borderBottom:index === candidates.length - 1 ? "none" : "1px solid #27272a"}}>
          <div style={{display:"flex",justifyContent:"space-between",gap:16,alignItems:"flex-start",flexWrap:"wrap"}}>
            <div><div style={{fontSize:12,color:"#a1a1aa",letterSpacing:1.2}}>{candidate.sport} · {candidate.thesis_type} · {candidate.stage}</div><h3 style={{fontSize:26,margin:"5px 0 7px"}}>{candidate.player}</h3><div style={{fontWeight:700}}>{candidate.headline}</div></div>
            <span style={{fontSize:11,border:"1px solid #3f3f46",borderRadius:999,padding:"6px 9px",color:candidate.source_quality === "CORROBORATED" ? "#86efac" : "#fbbf24"}}>{candidate.source_quality}</span>
          </div>
          <p style={{color:"#a1a1aa",lineHeight:1.55,maxWidth:860}}>{candidate.why_now}</p>
          <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(220px,1fr))",gap:10,marginTop:16}}>
            <div style={{background:"#09090b",border:"1px solid #27272a",borderRadius:12,padding:14}}><small style={{color:"#71717a"}}>TARGET CARD</small><div style={{marginTop:7,fontWeight:700}}>{candidate.card}</div></div>
            <div style={{background:"#09090b",border:"1px solid #27272a",borderRadius:12,padding:14}}><small style={{color:"#71717a"}}>CURRENT DECISION</small><div style={{marginTop:7,fontWeight:800,color:"#fbbf24"}}>{candidate.decision}</div><div style={{marginTop:6,color:"#a1a1aa",fontSize:13}}>{candidate.blocker}</div></div>
          </div>
          <div style={{display:"flex",justifyContent:"space-between",gap:14,marginTop:14,alignItems:"center",flexWrap:"wrap",fontSize:12,color:"#71717a"}}><span>Observed {formatObserved(candidate.observed_at)}</span><a href={candidate.source_url} target="_blank" rel="noreferrer" style={{color:"#d4d4d8"}}>Open catalyst source ↗</a></div>
        </article>)}
      </div>
    </section>

    <section style={{border:"1px solid #27272a",borderRadius:18,overflow:"hidden",background:"#111113",marginTop:34}}>
      <div style={{padding:20,borderBottom:"1px solid #27272a",display:"flex",justifyContent:"space-between",gap:20,alignItems:"center",flexWrap:"wrap"}}>
        <div><div style={{fontSize:12,color:"#a1a1aa",letterSpacing:1.3}}>AUTHORITATIVE RESEARCH</div><h2 style={{margin:"5px 0 0",fontSize:24}}>eBay Product Research queue</h2><p style={{margin:"8px 0 0",color:"#a1a1aa",maxWidth:720,lineHeight:1.5}}>These are the exact exports blocking a real decision. Pull the full result set for each window; the research runner fingerprints the CSV bytes, resolves the card, measures repricing, and returns START_POSITION / DO_NOT_CHASE / WATCH.</p></div>
        <span style={{fontSize:12,color:"#fbbf24"}}>{queue.length} EXPORTS MISSING</span>
      </div>
      <div>
        {queue.map((item, index) => <article key={item.card_id} style={{padding:20,borderBottom:index === queue.length - 1 ? "none" : "1px solid #27272a"}}>
          <div style={{display:"flex",justifyContent:"space-between",gap:16,alignItems:"flex-start",flexWrap:"wrap"}}>
            <div><div style={{fontSize:12,color:"#a1a1aa"}}>#{item.queue_position} · {item.collection_priority} · {item.window_status}</div><h3 style={{fontSize:21,margin:"5px 0"}}>{item.player}</h3><div style={{fontWeight:700}}>{item.card_label}</div></div>
            <span style={{fontSize:11,border:"1px solid #7c2d12",background:"#431407",borderRadius:999,padding:"6px 9px",color:"#fdba74"}}>{item.status}</span>
          </div>
          <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(210px,1fr))",gap:10,marginTop:16}}>
            <div style={{background:"#09090b",border:"1px solid #27272a",borderRadius:12,padding:14}}><small style={{color:"#71717a"}}>SOLD WINDOW</small><div style={{marginTop:7,fontWeight:700}}>{formatWindow(item.sold_window_start)} → {formatWindow(item.sold_window_end)}</div></div>
            <div style={{background:"#09090b",border:"1px solid #27272a",borderRadius:12,padding:14,minWidth:0}}><small style={{color:"#71717a"}}>EXPECTED EXPORT</small><div style={{marginTop:7,fontFamily:"ui-monospace,SFMono-Regular,monospace",fontSize:12,overflowWrap:"anywhere"}}>{item.expected_export_filename}</div></div>
          </div>
        </article>)}
      </div>
    </section>

    <section style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(180px,1fr))",gap:1,background:"#27272a",marginTop:34,border:"1px solid #27272a",borderRadius:16,overflow:"hidden"}}>{[['1','Discover'],['2','Underwrite'],['3','Clock'],['4','Target cards'],['5','Journal'],['6','Grade outcome']].map(([n,label]) => <div key={n} style={{background:"#111113",padding:18}}><span style={{color:"#71717a",fontSize:12}}>{n}</span><div style={{marginTop:16,fontWeight:700}}>{label}</div></div>)}</section>
  </main>;
}
