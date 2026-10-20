"""Build an offline, blinded HTML reviewer for complete video candidate sets."""

import argparse
import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
REQUIRED = {"video_id", "video_title", "ad_id", "ad_name", "ad_description"}


def verified_youtube_id(row):
    """Return a video ID only with a human verifier and verification date."""
    if str(row.get("source_video_url_verified", "")).strip().casefold() not in {"true", "yes", "1"}:
        return ""
    if not str(row.get("source_video_verified_by", "")).strip() or not str(row.get("source_video_verified_at", "")).strip():
        return ""
    try:
        parsed = urlparse(str(row.get("source_video_url", "")).strip())
    except ValueError:
        return ""
    host = (parsed.hostname or "").lower().removeprefix("www.")
    video_id = ""
    if parsed.scheme == "https" and host == "youtu.be":
        video_id = parsed.path.strip("/").split("/")[0]
    elif parsed.scheme == "https" and host in {"youtube.com", "m.youtube.com", "youtube-nocookie.com"}:
        if parsed.path == "/watch":
            video_id = parse_qs(parsed.query).get("v", [""])[0]
        elif parsed.path.startswith("/embed/"):
            video_id = parsed.path.split("/")[2]
    return video_id if len(video_id) == 11 and video_id.replace("_", "a").replace("-", "a").isalnum() else ""


def render_review_html(frame: pd.DataFrame) -> str:
    missing = REQUIRED - set(frame.columns)
    if missing:
        raise ValueError(f"Review packet is missing columns: {', '.join(sorted(missing))}")
    if frame.empty:
        raise ValueError("Review packet has no video-ad pairs")
    if frame.duplicated(["video_id", "ad_id"]).any():
        raise ValueError("Review packet contains duplicate video/ad identifiers")

    records = frame.fillna("").to_dict(orient="records")
    # Keep packet content inert in HTML and render all metadata through textContent.
    payload = json.dumps(records, ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    title = "AdMind human relevance review"
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>
:root {{ color-scheme: light; font: 16px/1.45 system-ui,sans-serif; color:#17202a; background:#f3f5f7; }}
body {{ max-width:1100px; margin:2rem auto; padding:0 1rem 4rem; }}
h1,h2,h3 {{ line-height:1.2 }}
.notice,.video,.ad {{ background:white; border:1px solid #d8dee6; border-radius:10px; padding:1rem; margin:1rem 0; }}
.notice {{ border-left:5px solid #9a6700 }}
.meta {{ color:#475569; font-size:.94rem }}
.ad-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(300px,1fr)); gap:.75rem }}
.ad {{ margin:0; }}
label {{ display:block; margin:.65rem 0 .2rem; font-weight:600 }}
select,textarea,button {{ font:inherit; }}
select,textarea {{ width:100%; box-sizing:border-box; padding:.45rem; }}
textarea {{ min-height:4rem }}
button {{ padding:.65rem 1rem; border:0; border-radius:6px; background:#1457a6; color:white; cursor:pointer }}
button:disabled {{ background:#64748b; cursor:not-allowed }}
</style>
</head>
<body>
<h1>{title}</h1>
<p>Review every candidate under each video together. This page contains no model ranks, scores, or selection cues. Save the downloaded CSV as a new review file; do not overwrite the source packet.</p>
<section class="notice"><strong>Video evidence:</strong> Source records have no verified video IDs. Footage is embedded only when the packet has a verified HTTPS YouTube URL, verifier, and verification date. Verify the video against its recorded title and channel before adding those fields. Otherwise judge recorded metadata only; mark <em>insufficient information</em> when it does not support a responsible judgment. Do not infer from category alone.</section>
<p id="progress" class="meta" aria-live="polite"></p>
<main id="reviews"></main>
<button id="export" type="button">Download reviewed CSV</button>
<p id="message" role="status" aria-live="polite"></p>
<script id="packet" type="application/json">{payload}</script>
<script>
"use strict";
const rows = JSON.parse(document.getElementById("packet").textContent);
const groups = new Map();
for (const row of rows) {{ if (!groups.has(row.video_id)) groups.set(row.video_id, []); groups.get(row.video_id).push(row); }}
const root = document.getElementById("reviews");
const text = (parent, tag, value, className) => {{ const el=document.createElement(tag); el.textContent=value || "Not provided"; if(className) el.className=className; parent.appendChild(el); return el; }};
for (const [videoId, candidates] of groups) {{
  const first=candidates[0], section=document.createElement("section"); section.className="video";
  text(section,"h2",first.video_title);
  text(section,"p",`Source: ${{first.source_dataset || "not provided"}}, row ${{first.source_row || "not provided"}} · Channel: ${{first.source_channel || "not provided"}} · Published: ${{first.source_published_at || "not provided"}}`,"meta");
  text(section,"p",`Recorded source category: ${{first.source_category || "not provided"}} (fit: ${{first.source_category_fit || "unverified"}}). Stable source-record key: ${{videoId}}; this is not a YouTube ID. Candidate count: ${{candidates.length}}.`,"meta");
  const verified=["true","yes","1"].includes(String(first.source_video_url_verified || "").trim().toLowerCase());
  const verifier=String(first.source_video_verified_by || "").trim(), verifiedAt=String(first.source_video_verified_at || "").trim();
  const rawUrl=String(first.source_video_url || "").trim();
  let videoIdForEmbed="";
  try {{
    const u=new URL(rawUrl), host=u.hostname.toLowerCase().replace(/^www\\./,"");
    if(u.protocol==="https:" && host==="youtu.be") videoIdForEmbed=u.pathname.split("/").filter(Boolean)[0] || "";
    if(u.protocol==="https:" && ["youtube.com","m.youtube.com","youtube-nocookie.com"].includes(host)) videoIdForEmbed=u.searchParams.get("v") || u.pathname.match(/^\\/embed\\/([A-Za-z0-9_-]{{11}})$/)?.[1] || "";
  }} catch {{}}
  if(verified && verifier && verifiedAt && /^[A-Za-z0-9_-]{{11}}$/.test(videoIdForEmbed)) {{
    const frame=document.createElement("iframe"); frame.title="Verified source video"; frame.width="560"; frame.height="315"; frame.loading="lazy"; frame.referrerPolicy="strict-origin-when-cross-origin"; frame.allowFullscreen=true; frame.src=`https://www.youtube-nocookie.com/embed/${{videoIdForEmbed}}`; section.appendChild(frame);
    text(section,"p",`Video URL verified by ${{verifier}} on ${{verifiedAt}}.`,"meta");
  }}
  const grid=document.createElement("div"); grid.className="ad-grid";
  for (const row of candidates) {{
    const card=document.createElement("article"); card.className="ad";
    text(card,"h3",row.ad_name);
    text(card,"p",row.ad_description);
    text(card,"p",`Ad category: ${{row.ad_category || "not provided"}} · Mode: ${{row.ad_mode || "not provided"}} · Ad ID: ${{row.ad_id}}`,"meta");
    const status=document.createElement("select"); status.setAttribute("aria-label",`Review status for ${{row.ad_name}}`);
    for (const [value,label] of [["pending","Pending"],["rated","Rated"],["insufficient_information","Insufficient information"]]) {{ const opt=document.createElement("option"); opt.value=value; opt.textContent=label; status.appendChild(opt); }}
    status.value=row.judgment_status || "pending";
    const statusLabel=text(card,"label","Judgment status"); statusLabel.appendChild(status);
    const relevance=document.createElement("select"); relevance.setAttribute("aria-label",`Relevance for ${{row.ad_name}}`);
    for (const [value,label] of [["","Choose 0–3"],["0","0 · Irrelevant"],["1","1 · Weak/incidental"],["2","2 · Relevant"],["3","3 · Highly relevant and useful"]]) {{ const opt=document.createElement("option"); opt.value=value; opt.textContent=label; relevance.appendChild(opt); }}
    relevance.value=row.relevance === "" ? "" : String(row.relevance);
    const relevanceLabel=text(card,"label","Relevance"); relevanceLabel.appendChild(relevance);
    const notes=document.createElement("textarea"); notes.value=row.label_notes || ""; notes.setAttribute("aria-label",`Reason or missing information for ${{row.ad_name}}`);
    const notesLabel=text(card,"label","Reason / missing information"); notesLabel.appendChild(notes);
    const sync=()=>{{ row.judgment_status=status.value; row.relevance=status.value === "rated" ? relevance.value : ""; row.label_notes=notes.value; relevance.disabled=status.value !== "rated"; }};
    status.addEventListener("change",sync); relevance.addEventListener("change",sync); notes.addEventListener("input",sync); sync();
    grid.appendChild(card);
  }}
  section.appendChild(grid); root.appendChild(section);
}}
const progress=()=>{{ const complete=[...groups.values()].filter(g=>g.every(r=>r.judgment_status==="rated" || r.judgment_status==="insufficient_information")).length; document.getElementById("progress").textContent=`${{groups.size}} video sets · ${{rows.length}} pairs · ${{complete}} sets fully reviewed (sets with insufficient-information rows remain excluded from metrics)`; }};
root.addEventListener("change",progress); root.addEventListener("input",progress); progress();
const quote=value=>`"${{String(value ?? "").replaceAll('"','""')}}"`;
document.getElementById("export").addEventListener("click",()=>{{
  const incomplete=rows.filter(r=>r.judgment_status==="rated" && !["0","1","2","3"].includes(String(r.relevance)));
  if(incomplete.length) {{ document.getElementById("message").textContent=`${{incomplete.length}} rows marked Rated need a 0–3 score.`; return; }}
  const headers=Object.keys(rows[0]); const csv=[headers.map(quote).join(","),...rows.map(r=>headers.map(k=>quote(r[k])).join(","))].join("\\r\\n");
  const blob=new Blob(["\\ufeff",csv],{{type:"text/csv;charset=utf-8"}}); const url=URL.createObjectURL(blob); const link=document.createElement("a"); link.href=url; link.download="recommendation-labels-reviewed.csv"; link.click(); URL.revokeObjectURL(url); document.getElementById("message").textContent="Downloaded. Keep this file separate from the source packet until it has been reviewed.";
}});
</script>
</body></html>
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="docs/recommendation-labels.csv")
    parser.add_argument("--output", default="artifacts/recommendation-review.html")
    args = parser.parse_args()
    source = Path(args.input)
    output = Path(args.output)
    if not source.is_absolute():
        source = ROOT / source
    if not output.is_absolute():
        output = ROOT / output
    frame = pd.read_csv(source, keep_default_na=False)
    document = render_review_html(frame)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(document, encoding="utf-8")
    print(json.dumps({"output": str(output), "videos": int(frame.video_id.nunique()), "pairs": len(frame), "labels_changed": 0}))


if __name__ == "__main__":
    main()
