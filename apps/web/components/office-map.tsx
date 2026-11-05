import { memo } from "react";

// Original, code-native pixel art. Coordinates share the same grid as actor routes.
function Plant({ x, y, scale = 1 }: { x: number; y: number; scale?: number }) {
  return <use href="#office-plant" transform={`translate(${x} ${y}) scale(${scale})`} />;
}
function Desk({ x, y, accent = "#73c5c8" }: { x: number; y: number; accent?: string }) {
  return <g transform={`translate(${x} ${y})`}>
    <rect x="2" y="8" width="76" height="42" fill="#1b283549" />
    <path d="M0 0h76v38H0z" fill="#b89469" /><path d="M3 3h70v29H3z" fill="#dfc59b" />
    <path d="M0 35h76v6H0z" fill="#76583f" /><path d="M7 7h30v20H7z" fill="#293b4c" />
    <path d="M10 10h24v13H10z" fill="#172d3c" /><path d="M13 13h14v2H13zM13 18h19v2H13z" fill={accent} />
    <path d="M19 27h7v4h-7zM14 30h18v2H14zM7 33h30v3H7z" fill="#596779" />
    <path d="M48 9h17v19H48z" fill="#f0e4c9" /><path d="M51 13h11v2H51zM51 18h8v2h-8z" fill="#9bafab" />
    <path d="M61 30h7v5h-7zM68 31h2v3h-2z" fill="#6b8982" />
    <path d="M18 52h26v17H18zM15 57h5v19h-5zM42 57h5v19h-5z" fill="#31495b" />
    <path d="M21 55h20v11H21zM23 71h15v4H23z" fill="#567287" />
  </g>;
}
function Room({ x, y, w, h, name, floor, door }: { x: number; y: number; w: number; h: number; name: string; floor: string; door: "top" | "bottom" }) {
  const middle = x + w / 2;
  return <g>
    <rect x={x - 7} y={y - 8} width={w + 14} height={h + 21} fill="#0c1c24" />
    <rect x={x} y={y} width={w} height={h} fill={`url(#${floor})`} />
    <path d={`M${x} ${y + h}V${y}H${x + w}V${y + h}`} fill="none" stroke="#716c60" strokeWidth="8" />
    <path d={`M${x - 3} ${y - 7}H${x + w + 3}`} stroke="#b3ad96" strokeWidth="7" />
    <path d={`M${x} ${y + h}H${x + w}`} stroke="#b5b09b" strokeWidth="8" />
    <path d={`M${middle - 18} ${door === "bottom" ? y + h : y}h36`} stroke="#b6b4a1" strokeWidth="10" />
    <path d={`M${middle - 18} ${door === "bottom" ? y + h : y}h36`} stroke="#d0c9af" strokeWidth="5" />
    <rect x={x + 10} y={y + 5} width="50" height="10" fill="#7da6ad" stroke="#e1d4b9" strokeWidth="3" />
    <path d={`M${x + 34} ${y + 1}v18`} stroke="#d0c3a8" strokeWidth="3" />
    <rect x={x + 12} y={y - 27} width={name.length * 7 + 22} height="20" rx="5" fill="#1b2b36" stroke="#485966" />
    <text x={x + 23} y={y - 13} fill="#e3e8e6" fontSize="11" fontFamily="monospace" fontWeight="700">{name}</text>
  </g>;
}

export const OfficeMap = memo(function OfficeMap() {
  return <svg className="office-map-art" viewBox="0 0 960 640" aria-hidden="true" shapeRendering="crispEdges">
    <defs>
      <pattern id="office-grass" width="32" height="32" patternUnits="userSpaceOnUse"><rect width="32" height="32" fill="#1c3b32" /><path d="M4 9h3v2H4zM25 25h2v3h-2zM18 4h3v1h-3z" fill="#294b3c" /><path d="M12 20h2v2h-2z" fill="#15342c" /></pattern>
      <pattern id="office-wood" width="64" height="30" patternUnits="userSpaceOnUse"><rect width="64" height="30" fill="#c4ae88" /><path d="M0 0h64M0 15h64M32 0v15M12 15v15" fill="none" stroke="#a18d70" /><path d="M2 2h25M35 18h22" stroke="#d6c39d" /></pattern>
      <pattern id="office-blue" width="24" height="24" patternUnits="userSpaceOnUse"><rect width="24" height="24" fill="#788b9d" /><path d="M0 0h12v12H0zM12 12h12v12H12z" fill="#8396a6" /><path d="M0 0h24v24H0z" fill="none" stroke="#65798c" /></pattern>
      <pattern id="office-cream" width="30" height="30" patternUnits="userSpaceOnUse"><rect width="30" height="30" fill="#c9c6ad" /><path d="M0 0h30v30H0z" fill="none" stroke="#afaf99" /></pattern>
      <radialGradient id="office-light"><stop stopColor="#f7d77c" stopOpacity=".28" /><stop offset="1" stopColor="#f7d77c" stopOpacity="0" /></radialGradient>
      <g id="office-plant"><path d="M-9 8h18l-3 13H-6z" fill="#8b7259" /><path d="M-7 9H7v4H-7z" fill="#bb9471" /><path d="M-3-15h7v25H-3z" fill="#426f4b" /><path d="M-11-8h8v13h-8zM4-12h8V2H4zM-7-16h13v11H-7z" fill="#568657" /><path d="M-5-17h7v7H-5zM4-9h5v5H4zM-9-5h5v4h-5z" fill="#80a96e" /></g>
      <g id="office-tree"><ellipse cx="0" cy="24" rx="23" ry="9" fill="#0c262854" /><path d="M-4 1h8v25h-8z" fill="#5d5746" /><path d="M-15-22h28v6h7v23h-6v6h-28V7h-7v-23h6z" fill="#294d41" /><path d="M-13-23H9v5h8v19h-7v6h-24V1h-5v-16h6z" fill="#386448" /><path d="M-10-20H6v6h-16zM-16-11h8v13h-8z" fill="#467956" /></g>
      <g id="office-pine"><path d="M-3 8h6v19h-6z" fill="#555442" /><path d="M-4-24h8v8h6v10h7V5h6v9h-46V5h6V-6h7v-10h6z" fill="#173c35" /><path d="M-3-21h6v9h6v9h6v10h-30V-3h6v-9h6z" fill="#315645" /><path d="M-8-1h16v3H-8zM-12 8h23v3h-23z" fill="#416b51" /></g>
      <g id="office-shelf"><rect width="53" height="21" fill="#715b49" /><path d="M3 3h47v14H3z" fill="#334149" /><path d="M5 4h5v11H5zM20 4h5v11h-5zM37 4h4v11h-4z" fill="#afa77a" /><path d="M12 4h6v11h-6zM27 5h7v10h-7zM43 4h5v11h-5z" fill="#6b8b86" /><path d="M0 20h53v5H0z" fill="#a58b65" /></g>
      <g id="office-chair"><path d="M-8-6H8v17H-8z" fill="#2d4856" /><path d="M-6-5H6v9H-6z" fill="#6c8f9c" /><path d="M-6 13H6v3H-6z" fill="#1c343f" /></g>
    </defs>
    <rect width="960" height="640" fill="url(#office-grass)" />
    {[35, 108, 201, 299, 389, 586, 681, 774, 866, 929].map((x, i) => <use key={x} href={i % 2 ? "#office-pine" : "#office-tree"} x={x} y={38 + (i % 3) * 7} />)}
    {[130, 230, 348, 452, 530].map((y, i) => <g key={y}><use href={i % 2 ? "#office-tree" : "#office-pine"} x={48 + (i % 2) * 34} y={y} /><use href={i % 2 ? "#office-pine" : "#office-tree"} x={891 + (i % 2) * 32} y={y - 12} /></g>)}
    <rect x="137" y="84" width="708" height="461" rx="3" fill="#10282b" />
    <rect x="145" y="79" width="694" height="460" fill="#4b5854" />
    <rect x="158" y="98" width="666" height="424" fill="url(#office-cream)" />
    <Room x={160} y={100} w={200} h={180} name="Recepção · CEO" floor="office-wood" door="bottom" />
    <Room x={376} y={100} w={205} h={180} name="Copa" floor="office-blue" door="bottom" />
    <Room x={597} y={100} w={225} h={180} name="Desenvolvimento" floor="office-wood" door="bottom" />
    <Room x={160} y={348} w={200} h={170} name="Criação" floor="office-wood" door="top" />
    <Room x={376} y={348} w={205} h={170} name="Convivência" floor="office-wood" door="top" />
    <Room x={597} y={348} w={225} h={170} name="Qualidade · QA" floor="office-blue" door="top" />
    {/* Reception: rug, visitor seating, coordinator desk and notice board. */}
    <rect x="179" y="218" width="61" height="39" fill="#73847a" /><path d="M181 220h57v35h-57z" fill="none" stroke="#9daba0" strokeWidth="2" />
    <path d="M178 180h55v24h-55zM175 179h8v29h-8zM230 179h8v29h-8z" fill="#8f5d45" /><path d="M184 182h42v15h-42z" fill="#be8c60" />
    <rect x="190" y="230" width="38" height="16" fill="#745d47" /><rect x="193" y="231" width="32" height="11" fill="#ccb28b" />
    <Desk x={270} y={131} accent="#b7dd95" />
    <rect x="186" y="123" width="47" height="27" fill="#70634f" /><rect x="189" y="126" width="41" height="21" fill="#ded1ac" /><path d="M194 130h15v5h-15zM212 132h13v9h-13z" fill="#91aba1" />
    <Plant x={176} y={127} /><Plant x={343} y={246} />
    {/* Kitchen counter and communal table. */}
    <path d="M388 120h179v30H388z" fill="#444f65" /><path d="M388 118h179v25H388z" fill="#c1c1b3" />
    <path d="M395 122h21v16h-21zM420 122h21v16h-21z" fill="#7d939d" /><path d="M399 125h13v10h-13zM424 125h13v10h-13z" fill="#405e73" />
    <path d="M450 119h22v21h-22zM480 120h15v19h-15z" fill="#384553" /><path d="M453 122h15v11h-15z" fill="#968f7b" />
    <path d="M538 111h26v31h-26z" fill="#99acb8" /><path d="M540 115h22v11h-22zM542 130h4v8h-4z" fill="#596e7a" />
    <rect x="435" y="179" width="96" height="37" fill="#a08a69" /><rect x="438" y="179" width="90" height="30" fill="#cbb792" />
    {[447, 474, 503, 525].map(x => <g key={x}><use href="#office-chair" x={x} y="164" /><use href="#office-chair" x={x} y="231" /></g>)}
    <path d="M451 188h6v7h-6zM480 194h5v6h-5zM507 185h7v7h-7z" fill="#dbdfcc" />
    <Plant x={561} y={255} />
    {/* DEV: two workstations, cabinets and a whiteboard. */}
    <Desk x={616} y={133} /><Desk x={736} y={133} accent="#94a4ed" />
    <use href="#office-shelf" x="648" y="242" /><use href="#office-shelf" x="746" y="242" />
    <path d="M699 119h24v47h-24z" fill="#e2d9bc" /><path d="M703 125h16M703 131h13M703 143h16M703 150h10" stroke="#839c91" strokeWidth="2" />
    <Plant x={809} y={115} />
    {/* Design studio: drafting desk, moodboard, stools and art materials. */}
    <Desk x={182} y={377} accent="#d4a5ce" /><Desk x={278} y={377} accent="#dfc17b" />
    <path d="M220 363h45v10h-45z" fill="#53695f" /><path d="M223 365h8v5h-8zM235 365h9v5h-9zM248 365h13v5h-13z" fill="#c7b995" />
    <use href="#office-shelf" x="181" y="480" /><Plant x={343} y={481} />
    {/* Lounge: rug, sofa, game table, floor lamp and book wall. */}
    <rect x="392" y="387" width="171" height="104" fill="#5e7357" /><path d="M397 393h160v91H397z" stroke="#8d9974" strokeWidth="2" fill="none" />
    <path d="M397 401h25v66h-25zM395 399h30v9h-30zM395 459h30v10h-30z" fill="#38596b" /><path d="M401 411h16v43h-16z" fill="#618797" />
    <path d="M507 395h42v33h-42zM503 393h8v39h-8zM545 393h8v39h-8z" fill="#375f77" /><path d="M513 399h29v22h-29z" fill="#638fa2" />
    <rect x="436" y="417" width="28" height="44" fill="#66543f" /><rect x="439" y="418" width="22" height="37" fill="#b79b72" /><path d="M445 427h10v13h-10z" fill="#8baba0" />
    <use href="#office-shelf" x="391" y="357" /><use href="#office-shelf" x="517" y="357" /><Plant x={560} y={495} />
    <circle cx="395" cy="473" r="24" fill="url(#office-light)" /><path d="M394 461h3v30h-3zM388 490h15v3h-15zM389 457h13l4 10h-21z" fill="#dfc58c" />
    {/* QA lab: review desks and equipment rack. */}
    <Desk x={615} y={380} accent="#e1c78a" /><Desk x={734} y={380} accent="#87c8b3" />
    <g transform="translate(90 87)"><rect x="695" y="363" width="28" height="48" fill="#3c4b59" /><path d="M698 367h22v10h-22zM698 381h22v10h-22zM698 395h22v10h-22z" fill="#203740" /><path d="M701 370h4v3h-4zM701 384h4v3h-4zM701 398h4v3h-4z" fill="#95bc9d" /></g>
    <use href="#office-shelf" x="620" y="480" /><Plant x={610} y={490} />
    {/* Open corridor and entrance; all routes follow these door gaps. */}
    <path d="M177 307h74M289 307h170M499 307h190M727 307h77" stroke="#adb3a2" strokeWidth="3" />
    <Plant x={170} y={301} scale={.8} /><Plant x={811} y={301} scale={.8} />
    <path d="M455 521h53v30h-53z" fill="url(#office-cream)" /><path d="M453 526h57" stroke="#92a194" strokeWidth="4" />
    <rect x="0" y="548" width="960" height="38" fill="#8b9485" /><path d="M0 550h960M0 572h960M0 585h960" stroke="#a9af98" strokeWidth="2" /><path d="M0 587h960v53H0z" fill="#283343" /><path d="M0 612h960" stroke="#6c7680" strokeWidth="2" strokeDasharray="18 14" />
    {[93, 278, 482, 681, 872].map(x => <g key={x}><circle cx={x} cy="558" r="38" fill="url(#office-light)" /><path d={`M${x - 2} 539h4v35h-4zM${x - 5} 573h10v3h-10z`} fill="#2c3b3d" /><path d={`M${x - 5} 534h10v10h-10z`} fill="#ddcf8c" /><path d={`M${x - 2} 536h4v6h-4z`} fill="#f3e8aa" /></g>)}
    {[174, 323, 623, 779].map(x => <Plant key={x} x={x} y={534} scale={.6} />)}
    <text x="163" y="61" fill="#93baa5" fontSize="11" fontFamily="monospace" letterSpacing="3">AI TEAM / CAMPUS 01</text>
  </svg>;
});

export function AgentSprite({ variant }: { variant: number }) {
  const skin = ["#d8a27b", "#f0c6a0", "#b67d62"][variant % 3];
  const hair = ["#36313d", "#d4bd83", "#443c43", "#6e4940"][variant % 4];
  return <svg viewBox="0 0 24 34" className="agent-sprite" aria-hidden="true" shapeRendering="crispEdges">
    <ellipse cx="12" cy="31" rx="10" ry="3" fill="#17232d66" />
    <g className="sprite-body"><path d="M6 15h12v12H6zM4 18h3v7H4zM17 18h3v7h-3z" fill="currentColor" />
      <path d="M7 6h10v11H7zM5 8h3v7H5zM16 8h3v7h-3z" fill={skin} />
      <path d={variant % 2 ? "M6 3h12v7H6zM16 7h3v10h-3z" : "M6 3h12v6H6zM5 6h3v7H5z"} fill={hair} />
      <path d="M8 10h2v2H8zM14 10h2v2h-2z" fill="#253346" /><path d="M10 14h4v1h-4z" fill="#9b6753" />
      {variant === 0 && <path d="M6 9h5v4H6zM13 9h5v4h-5zM11 10h2v1h-2z" fill="#526979" />}
      <path className="sprite-arm-left" d="M4 22h3v5H4z" fill={skin} /><path className="sprite-arm-right" d="M17 22h3v5h-3z" fill={skin} />
      <path d="M8 17h8v2H8z" fill="#ffffff33" />
    </g>
    <path className="sprite-leg-left" d="M7 26h4v6H6v-2h1z" fill="#273341" />
    <path className="sprite-leg-right" d="M13 26h4v4h1v2h-5z" fill="#273341" />
  </svg>;
}

export const agentPlaces = [
  { x: 28, y: 33, room: "Recepção", door: 27.1 },
  { x: 77, y: 33, room: "Desenvolvimento", door: 73.9 },
  { x: 23.2, y: 70, room: "Criação", door: 27.1 },
  { x: 77, y: 72, room: "Qualidade", door: 73.9 },
  { x: 51.5, y: 37.5, room: "Copa", door: 49.8 },
  { x: 33.2, y: 71, room: "Criação", door: 27.1 },
  { x: 55, y: 75, room: "Convivência", door: 49.8 },
];
