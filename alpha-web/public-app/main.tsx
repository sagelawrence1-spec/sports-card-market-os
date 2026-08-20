import { StrictMode, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import Home from "../app/page";
import RadarPage from "../app/radar/page";
import "../app/globals.css";

const root = document.getElementById("root");

if (!root) {
  throw new Error("Market OS could not find its application root.");
}

function PublicApp() {
  const [surface, setSurface] = useState(() => window.location.hash === "#radar" ? "radar" : "market");

  useEffect(() => {
    const syncSurface = () => setSurface(window.location.hash === "#radar" ? "radar" : "market");
    window.addEventListener("hashchange", syncSurface);
    return () => window.removeEventListener("hashchange", syncSurface);
  }, []);

  return <>
    <div style={{position:"fixed",right:14,bottom:14,zIndex:1000,display:"flex",gap:8,background:"rgba(9,9,11,.94)",border:"1px solid #3f3f46",borderRadius:999,padding:6,boxShadow:"0 12px 36px rgba(0,0,0,.35)"}} aria-label="Product surfaces">
      <a href="#" style={{color:surface === "market" ? "#09090b" : "#d4d4d8",background:surface === "market" ? "#f4f4f5" : "transparent",textDecoration:"none",fontWeight:800,fontSize:12,padding:"8px 12px",borderRadius:999}}>MARKET</a>
      <a href="#radar" style={{color:surface === "radar" ? "#09090b" : "#fbbf24",background:surface === "radar" ? "#fbbf24" : "transparent",textDecoration:"none",fontWeight:800,fontSize:12,padding:"8px 12px",borderRadius:999}}>RADAR</a>
    </div>
    {surface === "radar" ? <RadarPage /> : <Home />}
  </>;
}

createRoot(root).render(
  <StrictMode>
    <PublicApp />
  </StrictMode>,
);