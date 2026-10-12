import { upload } from "@vercel/blob/client";

const MAX_UPLOAD_BYTES = 100 * 1024 * 1024;

const form = document.querySelector(".upload-form");
const fileInput = document.querySelector("#pdf_file");
const submitButton = form?.querySelector('button[type="submit"]');
const statusPanel = form?.querySelector(".upload-status");
const statusText = form?.querySelector("[data-upload-status]");
const percentText = form?.querySelector("[data-upload-percent]");
const progress = form?.querySelector("[data-upload-progress]");
let inFlight = false;

function safeFilename(filename) {
  const stem = filename.replace(/\.pdf$/i, "");
  const cleaned = stem
    .normalize("NFKD")
    .replace(/[^A-Za-z0-9._-]+/g, "-")
    .replace(/^[._-]+|[._-]+$/g, "")
    .slice(0, 80);
  return `${cleaned || "upload"}.pdf`;
}

function showStatus(message, percentage = null) {
  statusPanel.hidden = false;
  statusText.textContent = message;

  if (percentage === null) {
    percentText.textContent = "";
    progress.removeAttribute("value");
  } else {
    const rounded = Math.round(percentage);
    percentText.textContent = `${rounded}%`;
    progress.value = rounded;
  }
}

function restoreForm(message) {
  window.X1Scenery?.reset();
  inFlight = false;
  submitButton.disabled = false;
  submitButton.textContent = "Generate PDFs";
  showStatus(message, 0);
}

if (form) {
  form.addEventListener("submit", async (event) => {
    const blobEnabled = form.dataset.blobUploadEnabled === "true";
    if (blobEnabled || inFlight) event.preventDefault();
    if (inFlight) return;

    const file = fileInput.files?.[0];
    if (!file) {
      event.preventDefault();
      restoreForm("Please choose a PDF file first.");
      return;
    }
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      event.preventDefault();
      restoreForm("Only PDF files are supported.");
      return;
    }
    const maxBytes = Number(form.dataset.maxUploadBytes) || MAX_UPLOAD_BYTES;
    if (file.size > maxBytes) {
      event.preventDefault();
      restoreForm(`This PDF is larger than the ${maxBytes / 1024 / 1024} MB upload limit.`);
      return;
    }

    inFlight = true;
    submitButton.disabled = true;
    submitButton.textContent = "Working...";

    try {
      window.X1Scenery?.start();
      if (!blobEnabled) {
        showStatus("Preparing your PDFs...");
        window.X1Scenery?.navigate();
        return; // Keep the existing multipart form and server redirect.
      }
      showStatus("Uploading PDF...", 0);
      const uploadId = crypto.randomUUID().replaceAll("-", "");
      const pathname = `x1-inputs/${uploadId}-${safeFilename(file.name)}`;
      const blob = await upload(pathname, file, {
        access: "private",
        handleUploadUrl: "/api/blob-upload",
        contentType: "application/pdf",
        onUploadProgress: ({ percentage }) => {
          showStatus("Uploading PDF...", percentage);
        },
      });

      showStatus("Upload complete. Preparing your PDFs...");
      const response = await fetch("/generate-from-blob", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          blob_pathname: blob.pathname,
          source_name: file.name,
          independent_outputs: true,
        }),
      });
      const result = await response.json();

      if (!response.ok || !result.result_url) {
        throw new Error(result.error || "Generation failed.");
      }

      window.X1Scenery?.navigate(result.result_url);
      window.location.assign(result.result_url);
    } catch (error) {
      event.preventDefault();
      restoreForm(error instanceof Error ? error.message : "Upload failed. Please try again.");
    }
  });
  window.addEventListener("pageshow", (event) => {
    if (event.persisted) restoreForm("Choose a PDF to generate again.");
  });
}
