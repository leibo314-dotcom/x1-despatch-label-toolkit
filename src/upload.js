import { upload } from "@vercel/blob/client";

const MAX_UPLOAD_BYTES = 100 * 1024 * 1024;

const form = document.querySelector(".upload-form");
const fileInput = document.querySelector("#pdf_file");
const submitButton = form?.querySelector('button[type="submit"]');
const statusPanel = form?.querySelector(".upload-status");
const statusText = form?.querySelector("[data-upload-status]");
const percentText = form?.querySelector("[data-upload-percent]");
const progress = form?.querySelector("[data-upload-progress]");

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
  submitButton.disabled = false;
  submitButton.innerHTML = 'Generate PDF <span aria-hidden="true">→</span>';
  showStatus(message, 0);
}

if (form?.dataset.blobUploadEnabled === "true") {
  form.addEventListener("submit", async (event) => {
    event.preventDefault();

    const file = fileInput.files?.[0];
    if (!file) {
      restoreForm("Please choose a PDF file first.");
      return;
    }
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      restoreForm("Only PDF files are supported.");
      return;
    }
    if (file.size > MAX_UPLOAD_BYTES) {
      restoreForm("This PDF is larger than the 100 MB upload limit.");
      return;
    }

    submitButton.disabled = true;
    submitButton.textContent = "Working...";
    showStatus("Uploading PDF...", 0);

    const uploadId = crypto.randomUUID().replaceAll("-", "");
    const pathname = `x1-inputs/${uploadId}-${safeFilename(file.name)}`;

    try {
      const blob = await upload(pathname, file, {
        access: "private",
        handleUploadUrl: "/api/blob-upload",
        contentType: "application/pdf",
        onUploadProgress: ({ percentage }) => {
          showStatus("Uploading PDF...", percentage);
        },
      });

      showStatus("Upload complete. Generating delivery PDF...");
      const response = await fetch("/generate-from-blob", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          blob_pathname: blob.pathname,
          source_name: file.name,
        }),
      });
      const result = await response.json();

      if (!response.ok || !result.result_url) {
        throw new Error(result.error || "Generation failed.");
      }

      window.location.assign(result.result_url);
    } catch (error) {
      restoreForm(error instanceof Error ? error.message : "Upload failed. Please try again.");
    }
  });
}
