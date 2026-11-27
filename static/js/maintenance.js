// static/js/maintenance.js — PERSON 3
// Small "progressive enhancement" helpers. Every page still WORKS without
// JavaScript (the server validates everything); JS only makes it nicer.

document.addEventListener("DOMContentLoaded", () => {
  setupPhotoPreview();
  setupAutoSubmitFilters();
  setupClickableRows();
  setupConfirmButtons();
  setupBillCalculator();
  setupMockPayment();
  setupStatusForm();
  setupDialogs();
});

// 1. Complaint form: preview the photo and catch bad files BEFORE uploading.
function setupPhotoPreview() {
  const input = document.getElementById("photo-input");
  if (!input) return;
  const preview = document.getElementById("photo-preview");
  const error = document.getElementById("photo-error");
  const maxBytes = Number(input.dataset.maxMb) * 1024 * 1024;
  const allowed = ["image/jpeg", "image/png", "image/webp"];

  input.addEventListener("change", () => {
    error.hidden = true;
    preview.hidden = true;
    const file = input.files[0];
    if (!file) return;

    let problem = "";
    if (!allowed.includes(file.type)) problem = "Please choose a JPG, PNG or WEBP image.";
    else if (file.size > maxBytes) problem = `That photo is ${(file.size / 1048576).toFixed(1)} MB — the limit is ${input.dataset.maxMb} MB.`;

    if (problem) {
      error.textContent = problem;
      error.hidden = false;
      input.value = "";               // clear the bad file
      return;
    }
    // URL.createObjectURL shows the local file without uploading it.
    preview.src = URL.createObjectURL(file);
    preview.hidden = false;
  });
}

// 2. Filter dropdowns submit themselves when changed.
function setupAutoSubmitFilters() {
  document.querySelectorAll(".auto-submit").forEach((el) =>
    el.addEventListener("change", () => el.form.submit())
  );
}

// 3. Click anywhere on a table row to open it.
function setupClickableRows() {
  document.querySelectorAll("tr.clickable").forEach((row) =>
    row.addEventListener("click", (e) => {
      if (e.target.closest("a, button")) return;   // let real links work normally
      window.location = row.dataset.href;
    })
  );
}

// 4. <button data-confirm="Are you sure?"> asks before submitting.
function setupConfirmButtons() {
  document.querySelectorAll("[data-confirm]").forEach((btn) =>
    btn.addEventListener("click", (e) => {
      if (!window.confirm(btn.dataset.confirm)) e.preventDefault();
    })
  );
}

// 5. Generate-bills page: live per-flat and grand totals.
function setupBillCalculator() {
  const grand = document.getElementById("grand-total");
  if (!grand) return;
  const form = grand.closest("form");
  const fmt = (n) => "₹" + n.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

  const selectAll = document.getElementById("select-all");
  selectAll.addEventListener("change", () => {
    form.querySelectorAll(".flat-check").forEach((c) => (c.checked = selectAll.checked));
    recalc();
  });

  function recalc() {
    const maint = parseFloat(form.maintenance_amount.value) || 0;
    const waterDefault = parseFloat(form.water_amount.value) || 0;
    let total = 0;
    form.querySelectorAll("tbody tr").forEach((row) => {
      const checked = row.querySelector(".flat-check").checked;
      const override = row.querySelector(".water-override").value;
      const water = override === "" ? waterDefault : parseFloat(override) || 0;
      const flatTotal = maint + water;
      row.querySelector(".flat-total").textContent = checked ? fmt(flatTotal) : "—";
      row.classList.toggle("muted", !checked);
      if (checked) total += flatTotal;
    });
    grand.textContent = fmt(total);
  }

  form.querySelectorAll(".bill-calc").forEach((el) => el.addEventListener("input", recalc));
  recalc();
}

// 6. Mock payment: show a "processing" state, disable the button so the
//    form can't be double-submitted, then let the real POST go through.
function setupMockPayment() {
  const form = document.getElementById("pay-form");
  if (!form) return;
  let submitted = false;
  form.addEventListener("submit", (e) => {
    if (submitted) { e.preventDefault(); return; }   // block double clicks
    e.preventDefault();
    submitted = true;
    document.getElementById("pay-btn").disabled = true;
    document.getElementById("processing").hidden = false;
    setTimeout(() => form.submit(), 1500);            // fake bank delay
  });
}

// 7. Complaint "Post an update" form: make the photo required when staff
//    choose Fixed, and the note required for a progress update.
//    (The server checks the same rules — this just warns earlier.)
function setupStatusForm() {
  const form = document.getElementById("status-form");
  if (!form) return;
  const select = form.querySelector("select[name=status]");
  const note = form.querySelector("input[name=note]");
  const photo = form.querySelector("input[name=photo]");
  const hint = document.getElementById("photo-hint");
  const proofRequired = form.dataset.proofRequired === "1";

  function update() {
    const fixing = select.value === "Fixed";
    const progress = select.value === form.dataset.current;
    photo.required = fixing && proofRequired;
    hint.textContent = photo.required ? "(required: proof of fix)" : "(optional)";
    note.required = progress;
    note.placeholder = progress ? "What did you do today? (required)" : "What was done?";
  }
  select.addEventListener("change", update);
  update();
}

// 8. Pop-ups: <button data-open-dialog="some-id"> opens <dialog id="some-id">.
//    Closes with the ✕ button, the Esc key (built in), or a click outside it.
function setupDialogs() {
  document.querySelectorAll("[data-open-dialog]").forEach((btn) =>
    btn.addEventListener("click", () =>
      document.getElementById(btn.dataset.openDialog).showModal()
    )
  );
  document.querySelectorAll("dialog").forEach((dialog) => {
    dialog.querySelectorAll("[data-close-dialog]").forEach((b) =>
      b.addEventListener("click", () => dialog.close())
    );
    // A click on the dark backdrop lands on the <dialog> element itself.
    dialog.addEventListener("click", (e) => { if (e.target === dialog) dialog.close(); });
  });
}
