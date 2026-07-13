// 911 Valuator frontend — vanilla JS, no build step.
// Photos are held in memory client-side and posted as multipart form data;
// the backend is stateless and never persists them.

const form = document.getElementById("valuation-form");
const dropzone = document.getElementById("dropzone");
const photoInput = document.getElementById("photo-input");
const browseBtn = document.getElementById("browse-btn");
const thumbs = document.getElementById("thumbs");
const submitBtn = document.getElementById("submit-btn");
const statusCard = document.getElementById("status");
const reportCard = document.getElementById("report");

const MAX_PHOTOS = 5;
let photos = []; // File objects, in memory only

// --- Photo handling ---------------------------------------------------------

browseBtn.addEventListener("click", () => photoInput.click());
photoInput.addEventListener("change", () => addPhotos(photoInput.files));

["dragover", "dragenter"].forEach((evt) =>
  dropzone.addEventListener(evt, (e) => {
    e.preventDefault();
    dropzone.classList.add("dragover");
  })
);
["dragleave", "drop"].forEach((evt) =>
  dropzone.addEventListener(evt, (e) => {
    e.preventDefault();
    dropzone.classList.remove("dragover");
  })
);
dropzone.addEventListener("drop", (e) => addPhotos(e.dataTransfer.files));

function addPhotos(fileList) {
  for (const file of fileList) {
    if (!file.type.startsWith("image/")) continue;
    if (photos.length >= MAX_PHOTOS) break;
    photos.push(file);
  }
  renderThumbs();
}

function renderThumbs() {
  thumbs.innerHTML = "";
  photos.forEach((file, i) => {
    const wrap = document.createElement("div");
    wrap.className = "thumb";
    const img = document.createElement("img");
    img.src = URL.createObjectURL(file);
    img.onload = () => URL.revokeObjectURL(img.src);
    const del = document.createElement("button");
    del.type = "button";
    del.textContent = "×";
    del.onclick = () => {
      photos.splice(i, 1);
      renderThumbs();
    };
    wrap.append(img, del);
    thumbs.append(wrap);
  });
}

// --- Submit -----------------------------------------------------------------

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  submitBtn.disabled = true;
  reportCard.classList.add("hidden");
  statusCard.classList.remove("hidden");

  const data = new FormData(form);
  photos.forEach((p) => data.append("photos", p, p.name));

  try {
    const res = await fetch("/api/valuate", { method: "POST", body: data });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      const msg =
        res.status === 429
          ? "Rate limit reached — please try again later."
          : err.detail || err.error || `Server error (${res.status})`;
      throw new Error(msg);
    }
    renderReport(await res.json());
  } catch (err) {
    reportCard.innerHTML = `<p class="error">Valuation failed: ${escapeHtml(err.message)}</p>`;
    reportCard.classList.remove("hidden");
  } finally {
    statusCard.classList.add("hidden");
    submitBtn.disabled = false;
  }
});

// --- Report rendering -------------------------------------------------------

const usd = (n) =>
  n.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });

function escapeHtml(s) {
  const div = document.createElement("div");
  div.textContent = s;
  return div.innerHTML;
}

function renderReport(r) {
  const drivers = (r.value_drivers || [])
    .map(
      (d) =>
        `<li class="dir-${d.direction}">${d.direction === "up" ? "▲" : "▼"} ${escapeHtml(
          d.factor
        )} <span class="muted">(${d.impact})</span></li>`
    )
    .join("");

  const comps = (r.comparable_sales || [])
    .map(
      (c) => `
      <div class="comp">
        <div>${escapeHtml(c.description)}<div class="source">${escapeHtml(c.source)}</div></div>
        <div class="price">${usd(c.price_usd)}</div>
      </div>`
    )
    .join("");

  const findings = (r.photo_findings || [])
    .map((f) => `<li>${escapeHtml(f)}</li>`)
    .join("");

  const caveats = (r.caveats || []).map((c) => `<li>${escapeHtml(c)}</li>`).join("");

  reportCard.innerHTML = `
    <h2>Valuation report</h2>
    <div class="range">
      <div class="point">${usd(r.point_estimate_usd)}</div>
      <div class="low-high">${usd(r.estimated_value_low_usd)} – ${usd(r.estimated_value_high_usd)}</div>
    </div>
    <div class="badges">
      <span class="badge">Confidence: ${escapeHtml(r.confidence)}</span>
      <span class="badge">Condition: ${escapeHtml(r.condition_grade)}</span>
    </div>
    <p>${escapeHtml(r.summary)}</p>
    ${findings ? `<div class="report-section"><h3>Photo findings</h3><ul>${findings}</ul></div>` : ""}
    ${drivers ? `<div class="report-section"><h3>Value drivers</h3><ul>${drivers}</ul></div>` : ""}
    ${comps ? `<div class="report-section"><h3>Comparable sales</h3>${comps}</div>` : ""}
    ${caveats ? `<div class="report-section"><h3>Caveats</h3><ul>${caveats}</ul></div>` : ""}
  `;
  reportCard.classList.remove("hidden");
  reportCard.scrollIntoView({ behavior: "smooth" });
}
