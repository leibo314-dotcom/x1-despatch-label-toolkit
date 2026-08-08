import { handleUpload } from "@vercel/blob/client";

const MAX_UPLOAD_BYTES = 100 * 1024 * 1024;
const BLOB_PATH_RE = /^x1-inputs\/[0-9a-f]{32}-[A-Za-z0-9][A-Za-z0-9._-]{0,99}\.pdf$/;

function isAllowedPreviewOrigin(request) {
  const getHeader = (name) => {
    if (typeof request.headers?.get === "function") {
      return request.headers.get(name);
    }
    const value = request.headers?.[name.toLowerCase()];
    return Array.isArray(value) ? value[0] : value;
  };
  const origin = getHeader("origin");
  const fetchSite = getHeader("sec-fetch-site");
  if (!origin || (fetchSite && fetchSite !== "same-origin")) {
    return false;
  }

  let hostname;
  try {
    hostname = new URL(origin).hostname.toLowerCase();
  } catch {
    return false;
  }

  const systemHosts = new Set(
    [process.env.VERCEL_URL, process.env.VERCEL_BRANCH_URL]
      .filter(Boolean)
      .map((host) => host.toLowerCase()),
  );
  const isProjectPreview =
    hostname.startsWith("x1-despatch-label-toolkit-") &&
    hostname.endsWith("-leibo314-dotcoms-projects.vercel.app");

  return systemHosts.has(hostname) || isProjectPreview;
}

async function readJsonBody(request) {
  if (request.body && typeof request.body === "object") {
    return request.body;
  }
  if (typeof request.body === "string") {
    return JSON.parse(request.body);
  }

  const chunks = [];
  for await (const chunk of request) {
    chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk));
  }
  return JSON.parse(Buffer.concat(chunks).toString("utf8"));
}

export default async function handler(request, response) {
  if (request.method !== "POST") {
    return response.status(405).json({ error: "Method not allowed" });
  }

  try {
    const body = await readJsonBody(request);

    if (body?.type === "blob.generate-client-token" && !isAllowedPreviewOrigin(request)) {
      return response.status(403).json({ error: "Upload origin is not allowed" });
    }

    const jsonResponse = await handleUpload({
      body,
      request,
      onBeforeGenerateToken: async (pathname) => {
        if (!BLOB_PATH_RE.test(pathname) || pathname.includes("..")) {
          throw new Error("Invalid PDF upload path");
        }

        return {
          allowedContentTypes: ["application/pdf"],
          maximumSizeInBytes: MAX_UPLOAD_BYTES,
          addRandomSuffix: false,
          validUntil: Date.now() + 10 * 60 * 1000,
        };
      },
    });

    return response.status(200).json(jsonResponse);
  } catch (error) {
    return response.status(400).json({
      error: error instanceof Error ? error.message : "Upload failed",
    });
  }
}
