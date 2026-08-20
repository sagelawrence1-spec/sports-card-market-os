const lanes = [
  { name: "EDGE", meaning: "Weak signals before the market fully confirms them", state: "Discovery" },
  { name: "CATALYST", meaning: "Known event with a measurable timing window", state: "Clock" },
  { name: "QUANT", meaning: "Price/pop/liquidity dislocation visible in the data", state: "Measure" },
];

export default function RadarPage() {
  return <main style={{maxWidth:1120,margin:"0 auto",padding:"28px 18px 80px",fontFamily:"system-ui,-apple-system,sans-serif",color:"#f4f4f5",background:"#09090b",minHeight:"100vh"}}>
    <nav style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:48}}>
      <a href="../" style={{color:"#f4f4f5",textDecoration:"none",fontWeight:800}}>MARKET OS</a>
      <span style={{fontSize:12,color:"#a1a1aa",letterSpacing:1.5}}>OPPORTUNITY ENGINE · ALPHA</span>
    </nav>
    <section style={{marginBottom:34}}><div style={{fontSize:12,color:"#a1a1aa",letterSpacing:1.5,marginBottom:10}}>RADAR</div><h1 style={{fontSize:"clamp(38px,8vw,72px)",lineHeight:.95,letterSpacing:-3,margin:"0 0 18px"}}>Find the move<br/>before consensus.</h1><p style={{maxWidth:720,color:"#a1a1aa",fontSize:17,lineHeight:1.6}}>The Opportunity Engine asks one question: what is changing in the real world faster than the card market is pricing it? This surface is now part of the product. Live candidates remain locked until their source and comp evidence clear the engine gates.</p></section>
    <section style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(220px,1fr))",gap:12,marginBottom:34}}>{lanes.map(lane => <article key={lane.name} style={{border:"1px solid #27272a",borderRadius:16,padding:20,background:"#111113"}}><div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:30}}><b>{lane.name}</b><span style={{fontSize:11,border:"1px solid #3f3f46",borderRadius:999,padding:"5px 8px",color:"#a1a1aa"}}>{lane.state}</span></div><p style={{color:"#a1a1aa",lineHeight:1.5,margin:0}}>{lane.meaning}</p></article>)}</section>
    <section style={{border:"1px solid #27272a",borderRadius:18,overflow:"hidden",background:"#111113"}}><div style={{padding:20,borderBottom:"1px solid #27272a",display:"flex",justifyContent:"space-between",gap:20,alignItems:"center"}}><div><div style={{fontSize:12,color:"#a1a1aa",letterSpacing:1.3}}>ACTIVE RADAR</div><h2 style={{margin:"5px 0 0",fontSize:24}}>Candidate queue</h2></div><span style={{fontSize:12,color:"#fbbf24"}}>EVIDENCE GATED</span></div><div style={{padding:"48px 20px",textAlign:"center"}}><div style={{fontSize:32,marginBottom:10}}>◉</div><b style={{fontSize:20}}>No candidate is being promoted without proof.</b><p style={{color:"#a1a1aa",maxWidth:620,margin:"10px auto 0",lineHeight:1.6}}>Radar discoveries will appear here only when the engine can preserve the catalyst, timestamp the original call, identify targeted cards, and distinguish market confirmation from narrative noise. No fabricated opportunities.</p></div></section>
    <section style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(180px,1fr))",gap:1,background:"#27272a",marginTop:34,border:"1px solid #27272a",borderRadius:16,overflow:"hidden"}}>{[['1','Discover'],['2','Underwrite'],['3','Clock'],['4','Target cards'],['5','Journal'],['6','Grade outcome']].map(([n,label]) => <div key={n} style={{background:"#111113",padding:18}}><span style={{color:"#71717a",fontSize:12}}>{n}</span><div style={{marginTop:16,fontWeight:700}}>{label}</div></div>)}</section>
  </main>;
}
